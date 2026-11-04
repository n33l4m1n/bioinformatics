//! Pipeline files: a strict subset of TOML (strings, arrays of strings, `[[step]]` tables), so they stay valid
//! TOML if the engine later moves to the `toml` crate. Unknown keys are errors, not silently ignored.
//!
//! ```toml
//! name = "crambin-1ns"
//! description = "optional"
//!
//! [[step]]
//! name = "simulate"
//! command = ["python", "{pipeline_dir}/simulate.py"]   # argv, no shell
//! inputs = ["1crn.pdb"]                                 # must exist before the step; hashed
//! outputs = ["trajectory.dcd"]                          # must exist after the step; hashed
//! stdout = "simulation.log"                             # optional; default is a log in the run dir
//! expect = ["<sha256>  1crn.pdb"]                       # optional pins, checked after the step
//! ```

use std::collections::BTreeMap;

#[derive(Debug, Clone, PartialEq)]
pub struct Step {
    pub name: String,
    pub command: Vec<String>,
    pub inputs: Vec<String>,
    pub outputs: Vec<String>,
    pub stdout: Option<String>,
    pub expect: Vec<(String, String)>,
}

#[derive(Debug, PartialEq)]
pub struct Pipeline {
    pub name: String,
    pub description: Option<String>,
    pub steps: Vec<Step>,
}

#[derive(Debug)]
enum Value {
    Str(String),
    List(Vec<String>),
}

type Table = BTreeMap<String, (usize, Value)>;

pub fn parse(text: &str) -> Result<Pipeline, String> {
    let mut top = Table::new();
    let mut steps: Vec<(usize, Table)> = Vec::new();
    let mut lines = text.lines().enumerate();
    while let Some((i, raw)) = lines.next() {
        let n = i + 1;
        let line = strip_comment(raw).trim().to_string();
        if line.is_empty() {
            continue;
        }
        if line == "[[step]]" {
            steps.push((n, Table::new()));
            continue;
        }
        if line.starts_with('[') {
            return Err(format!("line {n}: only [[step]] tables are supported"));
        }
        let eq = line.find('=').ok_or_else(|| format!("line {n}: expected key = value"))?;
        let key = line[..eq].trim().to_string();
        if !is_name(&key) {
            return Err(format!("line {n}: bad key {key:?}"));
        }
        let mut value_text = line[eq + 1..].trim().to_string();
        if value_text.starts_with('[') {
            while !array_closed(&value_text) {
                let (_, more) = lines.next().ok_or_else(|| format!("line {n}: unterminated array"))?;
                value_text.push(' ');
                value_text.push_str(strip_comment(more).trim());
            }
        }
        let value = parse_value(&value_text).map_err(|e| format!("line {n}: {e}"))?;
        let table = match steps.last_mut() {
            Some((_, t)) => t,
            None => &mut top,
        };
        if table.insert(key.clone(), (n, value)).is_some() {
            return Err(format!("line {n}: duplicate key {key}"));
        }
    }

    let name = take_str(&mut top, "name")?.ok_or("missing top-level name")?;
    if !is_name(&name) {
        return Err(format!("pipeline name {name:?}: use letters, digits, - and _"));
    }
    let description = take_str(&mut top, "description")?;
    reject_unknown(&top)?;

    let mut parsed = Vec::new();
    for (line, mut t) in steps {
        let name = take_str(&mut t, "name")?.ok_or(format!("line {line}: step without a name"))?;
        if !is_name(&name) {
            return Err(format!("line {line}: step name {name:?}: use letters, digits, - and _"));
        }
        if parsed.iter().any(|s: &Step| s.name == name) {
            return Err(format!("line {line}: duplicate step name {name}"));
        }
        let command = take_list(&mut t, "command")?.unwrap_or_default();
        if command.is_empty() {
            return Err(format!("step {name}: command must be a non-empty array"));
        }
        let mut expect = Vec::new();
        for pin in take_list(&mut t, "expect")?.unwrap_or_default() {
            let (hex, path) = pin
                .split_once("  ")
                .filter(|(h, p)| h.len() == 64 && h.bytes().all(|b| b.is_ascii_hexdigit()) && !p.is_empty())
                .ok_or(format!("step {name}: expect entries are \"<sha256>  <path>\""))?;
            expect.push((hex.to_ascii_lowercase(), path.to_string()));
        }
        let step = Step {
            command,
            inputs: take_list(&mut t, "inputs")?.unwrap_or_default(),
            outputs: take_list(&mut t, "outputs")?.unwrap_or_default(),
            stdout: take_str(&mut t, "stdout")?,
            expect,
            name,
        };
        reject_unknown(&t)?;
        parsed.push(step);
    }
    if parsed.is_empty() {
        return Err("pipeline has no [[step]]".into());
    }
    Ok(Pipeline { name, description, steps: parsed })
}

fn is_name(s: &str) -> bool {
    !s.is_empty() && s.chars().all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
}

fn take_str(t: &mut Table, key: &str) -> Result<Option<String>, String> {
    match t.remove(key) {
        None => Ok(None),
        Some((_, Value::Str(s))) => Ok(Some(s)),
        Some((n, Value::List(_))) => Err(format!("line {n}: {key} must be a string")),
    }
}

fn take_list(t: &mut Table, key: &str) -> Result<Option<Vec<String>>, String> {
    match t.remove(key) {
        None => Ok(None),
        Some((_, Value::List(l))) => Ok(Some(l)),
        Some((n, Value::Str(_))) => Err(format!("line {n}: {key} must be an array of strings")),
    }
}

fn reject_unknown(t: &Table) -> Result<(), String> {
    match t.iter().next() {
        Some((k, (n, _))) => Err(format!("line {n}: unknown key {k}")),
        None => Ok(()),
    }
}

/// Drops a trailing `# comment`, ignoring `#` inside strings.
fn strip_comment(line: &str) -> &str {
    let mut quote = None;
    let mut escaped = false;
    for (i, c) in line.char_indices() {
        match quote {
            Some('"') if escaped => escaped = false,
            Some('"') if c == '\\' => escaped = true,
            Some(q) if c == q => quote = None,
            Some(_) => {}
            None if c == '"' || c == '\'' => quote = Some(c),
            None if c == '#' => return &line[..i],
            None => {}
        }
    }
    line
}

fn array_closed(text: &str) -> bool {
    let mut quote = None;
    let mut escaped = false;
    for c in text.chars() {
        match quote {
            Some('"') if escaped => escaped = false,
            Some('"') if c == '\\' => escaped = true,
            Some(q) if c == q => quote = None,
            Some(_) => {}
            None if c == '"' || c == '\'' => quote = Some(c),
            None if c == ']' => return true,
            None => {}
        }
    }
    false
}

fn parse_value(text: &str) -> Result<Value, String> {
    let chars: Vec<char> = text.chars().collect();
    let mut pos = 0;
    let value = match chars.first() {
        Some('"' | '\'') => Value::Str(parse_string(&chars, &mut pos)?),
        Some('[') => {
            pos += 1;
            let mut items = Vec::new();
            loop {
                skip_ws(&chars, &mut pos);
                match chars.get(pos) {
                    Some(']') => {
                        pos += 1;
                        break;
                    }
                    Some('"' | '\'') => items.push(parse_string(&chars, &mut pos)?),
                    _ => return Err("arrays may only hold strings".into()),
                }
                skip_ws(&chars, &mut pos);
                match chars.get(pos) {
                    Some(',') => pos += 1,
                    Some(']') => {}
                    _ => return Err("expected , or ] in array".into()),
                }
            }
            Value::List(items)
        }
        _ => return Err("only strings and arrays of strings are supported".into()),
    };
    skip_ws(&chars, &mut pos);
    if pos != chars.len() {
        return Err("unexpected text after value".into());
    }
    Ok(value)
}

fn skip_ws(chars: &[char], pos: &mut usize) {
    while chars.get(*pos).is_some_and(|c| c.is_whitespace()) {
        *pos += 1;
    }
}

fn parse_string(chars: &[char], pos: &mut usize) -> Result<String, String> {
    let quote = chars[*pos];
    *pos += 1;
    let mut out = String::new();
    loop {
        let c = *chars.get(*pos).ok_or("unterminated string")?;
        *pos += 1;
        match c {
            c if c == quote => return Ok(out),
            '\\' if quote == '"' => {
                let e = *chars.get(*pos).ok_or("unterminated string")?;
                *pos += 1;
                out.push(match e {
                    'n' => '\n',
                    't' => '\t',
                    '"' => '"',
                    '\\' => '\\',
                    _ => return Err(format!("unsupported escape \\{e}")),
                });
            }
            c => out.push(c),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_a_pipeline() {
        let p = parse(
            r#"
            name = "demo"   # trailing comment
            description = 'has # inside'

            [[step]]
            name = "a"
            command = [
              "python", "x.py",   # multi-line array
              "--flag=\"q\"",
            ]
            inputs = ["in.txt"]
            outputs = []
            stdout = "a.log"
            expect = ["E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855  in.txt"]

            [[step]]
            name = "b"
            command = ["true"]
            "#,
        )
        .unwrap();
        assert_eq!(p.name, "demo");
        assert_eq!(p.description.as_deref(), Some("has # inside"));
        assert_eq!(p.steps[0].command, ["python", "x.py", "--flag=\"q\""]);
        assert_eq!(p.steps[0].stdout.as_deref(), Some("a.log"));
        assert_eq!(p.steps[0].expect[0].0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
        assert_eq!(p.steps[1].inputs, Vec::<String>::new());
    }

    #[test]
    fn rejects_what_it_does_not_understand() {
        let bad = [
            ("command = [\"x\"]", "missing top-level name"),
            ("name = \"p\"\n[[step]]\nname = \"a\"\ncommand = [\"x\"]\nretries = \"3\"", "unknown key retries"),
            ("name = \"p\"\n[[step]]\nname = \"a\"\ncommand = []", "non-empty"),
            ("name = \"p\"\n[[step]]\nname = \"a\"\ncommand = [\"x\"]\n[[step]]\nname = \"a\"\ncommand = [\"y\"]", "duplicate step"),
            ("name = \"p\"\n[env]", "only [[step]]"),
            ("name = 3", "only strings"),
            ("name = \"p\"\n[[step]]\nname = \"a b\"\ncommand = [\"x\"]", "step name"),
            ("name = \"p\"\n[[step]]\nname = \"a\"\ncommand = [\"x\"]\nexpect = [\"abc  f\"]", "expect entries"),
            ("name = \"p\"", "no [[step]]"),
        ];
        for (text, want) in bad {
            let err = parse(text).unwrap_err();
            assert!(err.contains(want), "{text:?} gave {err:?}, wanted {want:?}");
        }
    }
}
