use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};

fn biorun(args: &[&dyn AsRef<std::ffi::OsStr>]) -> Output {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_biorun"));
    for a in args {
        cmd.arg(a);
    }
    cmd.output().unwrap()
}

fn workdir(name: &str) -> PathBuf {
    let d = std::env::temp_dir().join(format!("biorun-test-{name}-{}", std::process::id()));
    let _ = fs::remove_dir_all(&d);
    fs::create_dir_all(&d).unwrap();
    d
}

fn only_run(dir: &Path) -> PathBuf {
    let runs: Vec<PathBuf> = fs::read_dir(dir.join("biorun")).unwrap().map(|e| e.unwrap().path()).collect();
    assert_eq!(runs.len(), 1, "{runs:?}");
    runs.into_iter().next().unwrap()
}

#[test]
fn records_hashes_and_verifies() {
    let dir = workdir("ok");
    fs::write(dir.join("in.txt"), "hello\n").unwrap();
    fs::write(
        dir.join("p.toml"),
        r#"name = "demo"

[[step]]
name = "copy"
command = ["cp", "in.txt", "out.txt"]
inputs = ["in.txt"]
outputs = ["out.txt"]
expect = ["5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03  out.txt"]

[[step]]
name = "count"
command = ["wc", "-c", "out.txt"]
inputs = ["out.txt"]
outputs = ["count.txt"]
stdout = "count.txt"
"#,
    )
    .unwrap();

    let out = biorun(&[&"run", &dir.join("p.toml"), &"--workdir", &dir]);
    assert!(out.status.success(), "{}", String::from_utf8_lossy(&out.stderr));
    let run = only_run(&dir);

    let sums = fs::read_to_string(run.join("hashes.sha256")).unwrap();
    assert!(sums.contains("5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03  in.txt\n"));
    assert!(sums.contains("  out.txt\n") && sums.contains("  count.txt\n"));
    let record = fs::read_to_string(run.join("run.json")).unwrap();
    assert!(record.contains("\"status\": \"ok\""), "{record}");
    assert!(fs::read_to_string(dir.join("count.txt")).unwrap().contains('6'));
    assert!(run.join("pipeline.toml").exists());

    let ok = biorun(&[&"verify", &run]);
    assert!(ok.status.success(), "{}", String::from_utf8_lossy(&ok.stdout));

    fs::write(dir.join("out.txt"), "tampered\n").unwrap();
    fs::remove_file(dir.join("count.txt")).unwrap();
    let bad = biorun(&[&"verify", &run]);
    let report = String::from_utf8_lossy(&bad.stdout);
    assert_eq!(bad.status.code(), Some(1));
    assert!(report.contains("CHANGED  out.txt") && report.contains("MISSING  count.txt"), "{report}");
}

#[test]
fn failing_step_stops_the_run() {
    let dir = workdir("fail");
    fs::write(
        dir.join("p.toml"),
        "name = \"demo\"\n[[step]]\nname = \"boom\"\ncommand = [\"false\"]\n\
         [[step]]\nname = \"after\"\ncommand = [\"touch\", \"ran\"]\n",
    )
    .unwrap();
    let out = biorun(&[&"run", &dir.join("p.toml"), &"--workdir", &dir]);
    assert_eq!(out.status.code(), Some(1));
    assert!(!dir.join("ran").exists());
    let record = fs::read_to_string(only_run(&dir).join("run.json")).unwrap();
    assert!(record.contains("\"status\": \"failed\"") && record.contains("exit status 1"), "{record}");
}

#[test]
fn missing_input_and_wrong_pin_fail() {
    let dir = workdir("inputs");
    fs::write(
        dir.join("p.toml"),
        "name = \"demo\"\n[[step]]\nname = \"a\"\ncommand = [\"touch\", \"ran\"]\ninputs = [\"nope.txt\"]\n",
    )
    .unwrap();
    assert_eq!(biorun(&[&"run", &dir.join("p.toml"), &"--workdir", &dir]).status.code(), Some(1));
    assert!(!dir.join("ran").exists(), "step ran without its input");

    let dir = workdir("pin");
    fs::write(
        dir.join("p.toml"),
        "name = \"demo\"\n[[step]]\nname = \"a\"\ncommand = [\"touch\", \"x\"]\noutputs = [\"x\"]\n\
         expect = [\"0000000000000000000000000000000000000000000000000000000000000000  x\"]\n",
    )
    .unwrap();
    let out = biorun(&[&"run", &dir.join("p.toml"), &"--workdir", &dir]);
    assert_eq!(out.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&out.stderr).contains("expected 0000"));
}

#[test]
fn only_and_from_select_steps() {
    let dir = workdir("select");
    fs::write(
        dir.join("p.toml"),
        "name = \"demo\"\n[[step]]\nname = \"a\"\ncommand = [\"touch\", \"a\"]\n\
         [[step]]\nname = \"b\"\ncommand = [\"touch\", \"b\"]\n",
    )
    .unwrap();
    assert!(biorun(&[&"run", &dir.join("p.toml"), &"--workdir", &dir, &"--only", &"b"]).status.success());
    assert!(dir.join("b").exists() && !dir.join("a").exists());
    let out = biorun(&[&"run", &dir.join("p.toml"), &"--workdir", &dir, &"--from", &"c"]);
    assert_eq!(out.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&out.stderr).contains("steps are a, b"));
}

#[test]
fn hash_matches_sha256sum_format() {
    let dir = workdir("hash");
    fs::write(dir.join("f"), "abc").unwrap();
    let out = biorun(&[&"hash", &dir.join("f")]);
    let line = String::from_utf8_lossy(&out.stdout);
    assert!(line.starts_with("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad  "), "{line}");
}
