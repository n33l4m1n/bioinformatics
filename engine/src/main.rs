mod json;
mod run;
mod sha256;
mod spec;
mod time;

use std::path::{Path, PathBuf};
use std::process::ExitCode;

const USAGE: &str = "\
biorun: run a research pipeline and record its provenance

usage:
  biorun run <pipeline.toml> [--workdir DIR] [--from STEP | --only STEP]
  biorun verify <run-dir>
  biorun hash <file>...
  biorun --version";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match dispatch(&args) {
        Ok(code) => code,
        Err(e) => {
            eprintln!("biorun: {e}");
            ExitCode::from(2)
        }
    }
}

fn dispatch(args: &[String]) -> Result<ExitCode, String> {
    match args.first().map(String::as_str) {
        Some("run") => {
            let mut pipeline = None;
            let mut opts = run::Options::default();
            let mut it = args[1..].iter();
            while let Some(a) = it.next() {
                match a.as_str() {
                    "--workdir" => opts.workdir = Some(PathBuf::from(value(&mut it, a)?)),
                    "--from" => opts.from = Some(value(&mut it, a)?),
                    "--only" => opts.only = Some(value(&mut it, a)?),
                    s if s.starts_with("--") => return Err(format!("unknown option {s}\n\n{USAGE}")),
                    s if pipeline.is_none() => pipeline = Some(PathBuf::from(s)),
                    s => return Err(format!("unexpected argument {s}\n\n{USAGE}")),
                }
            }
            let pipeline = pipeline.ok_or_else(|| USAGE.to_string())?;
            run::run(&pipeline, &opts)
        }
        Some("verify") if args.len() == 2 => run::verify(Path::new(&args[1])),
        Some("hash") if args.len() >= 2 => {
            for f in &args[1..] {
                let h = sha256::file_hex(Path::new(f)).map_err(|e| format!("{f}: {e}"))?;
                println!("{h}  {f}");
            }
            Ok(ExitCode::SUCCESS)
        }
        Some("--version") => {
            println!("biorun {}", env!("CARGO_PKG_VERSION"));
            Ok(ExitCode::SUCCESS)
        }
        Some("-h" | "--help") => {
            println!("{USAGE}");
            Ok(ExitCode::SUCCESS)
        }
        _ => Err(USAGE.to_string()),
    }
}

fn value(it: &mut std::slice::Iter<String>, flag: &str) -> Result<String, String> {
    it.next().cloned().ok_or_else(|| format!("{flag} needs a value"))
}
