//! `biorun run` and `biorun verify`.
//!
//! A run lives in `<workdir>/biorun/<UTC stamp>-<pipeline>/`:
//! - `run.json`: who/what/when: pipeline hash, git commit + dirty flag, host, per-step argv, exit code, timing and
//!   input/output hashes. Rewritten after every step, so a killed run still says how far it got.
//! - `hashes.sha256`: every input and output, in `sha256sum` format relative to the workdir, so
//!   `cd <workdir> && sha256sum -c biorun/<run>/hashes.sha256` checks a run without biorun.
//! - `pipeline.toml`: the exact file that ran; `<step>.stderr.log` and, unless `stdout` is set, `<step>.stdout.log`.

use crate::json::J;
use crate::spec::{self, Pipeline, Step};
use crate::{sha256, time};
use std::collections::BTreeMap;
use std::fs::{self, File};
use std::path::{Path, PathBuf};
use std::process::{Command, ExitCode, Stdio};
use std::time::Instant;

#[derive(Default)]
pub struct Options {
    pub workdir: Option<PathBuf>,
    pub from: Option<String>,
    pub only: Option<String>,
}

pub fn run(pipeline_path: &Path, opts: &Options) -> Result<ExitCode, String> {
    let shown = pipeline_path.display();
    let text = fs::read_to_string(pipeline_path).map_err(|e| format!("{shown}: {e}"))?;
    let pipeline = spec::parse(&text).map_err(|e| format!("{shown}: {e}"))?;
    let pipeline_file = fs::canonicalize(pipeline_path).map_err(|e| format!("{shown}: {e}"))?;
    let pipeline_dir = pipeline_file.parent().unwrap_or(Path::new("/")).to_path_buf();
    let pipeline_dir_s = pipeline_dir.to_str().ok_or("pipeline path is not UTF-8")?.to_string();
    let steps = select(&pipeline, opts)?;

    let workdir = match &opts.workdir {
        Some(w) => w.clone(),
        None => std::env::current_dir().map_err(|e| e.to_string())?,
    };
    fs::create_dir_all(&workdir).map_err(|e| format!("{}: {e}", workdir.display()))?;
    let workdir = fs::canonicalize(&workdir).map_err(|e| e.to_string())?;

    let started = time::now();
    let run_dir = workdir.join("biorun").join(format!("{}-{}", time::stamp(started), pipeline.name));
    if run_dir.exists() {
        return Err(format!("{} already exists", run_dir.display()));
    }
    fs::create_dir_all(&run_dir).map_err(|e| format!("{}: {e}", run_dir.display()))?;
    fs::write(run_dir.join("pipeline.toml"), &text).map_err(|e| e.to_string())?;

    let subst = |s: &String| s.replace("{pipeline_dir}", &pipeline_dir_s);
    let (commit, dirty) = git_state(&pipeline_dir);
    let mut record = RunRecord {
        header: vec![
            ("biorun_version", J::str(env!("CARGO_PKG_VERSION"))),
            ("pipeline", J::str(&pipeline.name)),
            ("description", pipeline.description.as_ref().map_or(J::Null, J::str)),
            ("pipeline_file", J::str(pipeline_file.to_string_lossy())),
            ("pipeline_sha256", J::str(sha256::file_hex(&pipeline_file).map_err(|e| e.to_string())?)),
            ("git_commit", commit.map_or(J::Null, J::Str)),
            ("git_dirty", dirty.map_or(J::Null, J::Bool)),
            ("host", J::str(host())),
            ("workdir", J::str(workdir.to_string_lossy())),
            ("started", J::str(time::iso(started))),
        ],
        steps: Vec::new(),
        hashes: BTreeMap::new(),
    };

    for step in steps {
        eprintln!("biorun: {} ...", step.name);
        let outcome = run_step(step, &workdir, &run_dir, &subst, &mut record.hashes);
        let failed = outcome.error.clone();
        record.steps.push(outcome.into_json());
        if let Some(e) = failed {
            record.write(&run_dir, "failed", Some(time::now()))?;
            eprintln!("biorun: step {} failed: {e}\nbiorun: run record in {}", step.name, run_dir.display());
            return Ok(ExitCode::from(1));
        }
        record.write(&run_dir, "running", None)?;
    }
    record.write(&run_dir, "ok", Some(time::now()))?;
    println!("{}", run_dir.display());
    Ok(ExitCode::SUCCESS)
}

fn select<'a>(p: &'a Pipeline, opts: &Options) -> Result<&'a [Step], String> {
    let index = |name: &str| {
        p.steps.iter().position(|s| s.name == name).ok_or_else(|| {
            let names: Vec<&str> = p.steps.iter().map(|s| s.name.as_str()).collect();
            format!("no step {name:?}; steps are {}", names.join(", "))
        })
    };
    match (&opts.from, &opts.only) {
        (Some(_), Some(_)) => Err("use --from or --only, not both".into()),
        (Some(f), None) => Ok(&p.steps[index(f)?..]),
        (None, Some(o)) => {
            let i = index(o)?;
            Ok(&p.steps[i..=i])
        }
        (None, None) => Ok(&p.steps),
    }
}

struct Outcome {
    name: String,
    command: Vec<String>,
    exit_code: Option<i32>,
    seconds: f64,
    inputs: Vec<(String, String)>,
    outputs: Vec<(String, String)>,
    stdout: String,
    stderr: String,
    error: Option<String>,
}

impl Outcome {
    fn into_json(self) -> J {
        let pairs = |v: Vec<(String, String)>| J::Obj(v.into_iter().map(|(p, h)| (p, J::Str(h))).collect());
        J::obj(vec![
            ("name", J::Str(self.name)),
            ("command", J::Arr(self.command.into_iter().map(J::Str).collect())),
            ("exit_code", self.exit_code.map_or(J::Null, |c| J::Int(c as i64))),
            ("seconds", J::Float(self.seconds)),
            ("inputs", pairs(self.inputs)),
            ("outputs", pairs(self.outputs)),
            ("stdout", J::Str(self.stdout)),
            ("stderr", J::Str(self.stderr)),
            ("error", self.error.map_or(J::Null, J::Str)),
        ])
    }
}

fn run_step(
    step: &Step,
    workdir: &Path,
    run_dir: &Path,
    subst: &dyn Fn(&String) -> String,
    hashes: &mut BTreeMap<String, String>,
) -> Outcome {
    let command: Vec<String> = step.command.iter().map(subst).collect();
    let stdout_path = match &step.stdout {
        Some(p) => workdir.join(subst(p)),
        None => run_dir.join(format!("{}.stdout.log", step.name)),
    };
    let stderr_path = run_dir.join(format!("{}.stderr.log", step.name));
    let rel = |p: &Path| p.strip_prefix(workdir).unwrap_or(p).to_string_lossy().into_owned();
    let mut out = Outcome {
        name: step.name.clone(),
        command: command.clone(),
        exit_code: None,
        seconds: 0.0,
        inputs: Vec::new(),
        outputs: Vec::new(),
        stdout: rel(&stdout_path),
        stderr: rel(&stderr_path),
        error: None,
    };

    match hash_all(&step.inputs, workdir, subst, hashes) {
        Ok(h) => out.inputs = h,
        Err(e) => {
            out.error = Some(format!("input {e}"));
            return out;
        }
    }

    let files = File::create(&stdout_path).and_then(|o| File::create(&stderr_path).map(|e| (o, e)));
    let (stdout, stderr) = match files {
        Ok(f) => f,
        Err(e) => {
            out.error = Some(format!("can't create logs: {e}"));
            return out;
        }
    };
    let t0 = Instant::now();
    let status = Command::new(&command[0])
        .args(&command[1..])
        .current_dir(workdir)
        .stdin(Stdio::null())
        .stdout(stdout)
        .stderr(stderr)
        .status();
    out.seconds = t0.elapsed().as_secs_f64();
    match status {
        Err(e) => {
            out.error = Some(format!("can't start {}: {e}", command[0]));
            return out;
        }
        Ok(s) => {
            out.exit_code = s.code();
            if !s.success() {
                out.error = Some(match s.code() {
                    Some(c) => format!("exit status {c}; see {}", out.stderr),
                    None => "killed by a signal".to_string(),
                });
                return out;
            }
        }
    }

    match hash_all(&step.outputs, workdir, subst, hashes) {
        Ok(h) => out.outputs = h,
        Err(e) => {
            out.error = Some(format!("output {e}"));
            return out;
        }
    }
    for (want, path) in &step.expect {
        match sha256::file_hex(&workdir.join(subst(path))) {
            Ok(got) if &got == want => {}
            Ok(got) => {
                out.error = Some(format!("{path}: sha256 {got}, expected {want}"));
                return out;
            }
            Err(e) => {
                out.error = Some(format!("{path}: {e}"));
                return out;
            }
        }
    }
    out
}

fn hash_all(
    paths: &[String],
    workdir: &Path,
    subst: &dyn Fn(&String) -> String,
    hashes: &mut BTreeMap<String, String>,
) -> Result<Vec<(String, String)>, String> {
    let mut out = Vec::new();
    for p in paths {
        let p = subst(p);
        let h = sha256::file_hex(&workdir.join(&p)).map_err(|e| format!("{p}: {e}"))?;
        hashes.insert(p.clone(), h.clone());
        out.push((p, h));
    }
    Ok(out)
}

struct RunRecord {
    header: Vec<(&'static str, J)>,
    steps: Vec<J>,
    hashes: BTreeMap<String, String>,
}

impl RunRecord {
    fn write(&self, run_dir: &Path, status: &str, finished: Option<u64>) -> Result<(), String> {
        let mut pairs: Vec<(String, J)> = self.header.iter().map(|(k, v)| (k.to_string(), v.clone())).collect();
        pairs.push(("finished".into(), finished.map_or(J::Null, |t| J::str(time::iso(t)))));
        pairs.push(("status".into(), J::str(status)));
        pairs.push(("steps".into(), J::Arr(self.steps.clone())));
        write_atomic(&run_dir.join("run.json"), &J::Obj(pairs).pretty())?;
        let sums: String = self.hashes.iter().map(|(p, h)| format!("{h}  {p}\n")).collect();
        write_atomic(&run_dir.join("hashes.sha256"), &sums)
    }
}

fn write_atomic(path: &Path, text: &str) -> Result<(), String> {
    let tmp = path.with_extension("tmp");
    fs::write(&tmp, text).and_then(|_| fs::rename(&tmp, path)).map_err(|e| format!("{}: {e}", path.display()))
}

fn git_state(dir: &Path) -> (Option<String>, Option<bool>) {
    let git = |args: &[&str]| {
        Command::new("git")
            .arg("-C")
            .arg(dir)
            .args(args)
            .stderr(Stdio::null())
            .output()
            .ok()
            .filter(|o| o.status.success())
            .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
    };
    match git(&["rev-parse", "HEAD"]) {
        Some(commit) => (Some(commit), git(&["status", "--porcelain"]).map(|s| !s.is_empty())),
        None => (None, None),
    }
}

fn host() -> String {
    Command::new("uname")
        .arg("-n")
        .output()
        .ok()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .filter(|h| !h.is_empty())
        .unwrap_or_else(|| "unknown".into())
}

pub fn verify(run_dir: &Path) -> Result<ExitCode, String> {
    let run_dir = fs::canonicalize(run_dir).map_err(|e| format!("{}: {e}", run_dir.display()))?;
    let workdir = run_dir
        .parent()
        .and_then(Path::parent)
        .ok_or("expected <workdir>/biorun/<run>")?;
    let sums = run_dir.join("hashes.sha256");
    let text = fs::read_to_string(&sums).map_err(|e| format!("{}: {e}", sums.display()))?;
    let mut bad = 0;
    for line in text.lines().filter(|l| !l.is_empty()) {
        let (want, path) = line.split_once("  ").ok_or(format!("bad line in {}: {line}", sums.display()))?;
        let status = match sha256::file_hex(&workdir.join(path)) {
            Ok(got) if got == want => "OK",
            Ok(_) => "CHANGED",
            Err(_) => "MISSING",
        };
        if status != "OK" {
            bad += 1;
        }
        println!("{status}  {path}");
    }
    if bad > 0 {
        eprintln!("biorun: {bad} file(s) differ from the run record");
        return Ok(ExitCode::from(1));
    }
    Ok(ExitCode::SUCCESS)
}
