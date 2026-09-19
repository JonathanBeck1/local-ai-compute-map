#!/usr/bin/env python3
"""
Test suite for spend-gate.py. Self-contained: builds its own fixture scripts in
a temp dir and feeds each command to the hook exactly as Claude Code does (JSON
on stdin). Changes nothing on the machine.

    python3 test_spend_gate.py [path/to/spend-gate.py]

Exit status is the number of failures.

Every case in the "regression" groups is a bug found while building the gate.
They stay here so the same hole cannot reopen silently.
"""
import json
import os
import subprocess
import sys
import tempfile

GATE = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/.claude/hooks/spend-gate.py")


def decision(cmd):
    p = subprocess.run(
        ["python3", GATE],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}, "session_id": "test"}),
        capture_output=True, text=True, timeout=10)
    if p.returncode != 0:
        return f"EXIT{p.returncode}"
    if not p.stdout.strip():
        return "allow"
    return json.loads(p.stdout)["hookSpecificOutput"]["permissionDecision"]


def main():
    d = tempfile.mkdtemp(prefix="spend-gate-test-")
    fx = {
        "launch.sh": "#!/bin/bash\necho setting up\nsky launch -c gpu task.yaml\n",
        "harmless.sh": "#!/bin/bash\necho just listing\nsky status\n",
        "apostrophe.sh": "#!/bin/bash\n# we don't sky launch here, it's just a status check\nsky status\n",
        "burst.py": "import sky\ntask = sky.Task(run='nvidia-smi')\nsky.launch(task, cluster_name='x')\n",
    }
    for name, body in fx.items():
        path = os.path.join(d, name)
        with open(path, "w") as f:
            f.write(body)
        os.chmod(path, 0o755)
    T = d

    groups = [
        ("direct launches", "deny", [
            "sky launch -c gpu task.yaml", "sky jobs launch x.yaml", "sky start mycluster",
            "nohup sky serve up svc.yaml &", "aws --region us-east-1 ec2 run-instances --image-id ami-1",
            "gcloud compute instances create gpu-1 --zone us-c1", "az vm create -n x -g rg",
            'runpodctl create pod --gpuType "RTX 4090"', "vastai create instance 123",
            "dstack apply -f fleet.yml", "modal run app.py", "terraform apply -auto-approve",
            "pulumi up --yes", "aws sagemaker create-training-job --x y",
            "curl -X POST https://cloud.lambdalabs.com/api/v1/instance-operations/launch -d @x.json",
        ]),
        ("wrapped / indirect", "deny", [
            "SKYPILOT_DEBUG=1 sky launch t.yaml", "sudo -E sky launch t.yaml", "timeout 60 sky launch t.yaml",
            "cd /tmp && sky launch t.yaml", "ls; sky launch t.yaml", "true && sky launch t.yaml || echo fail",
            'bash -c "sky launch t.yaml"', "bash -lc 'cd x; sky launch t.yaml'", 'eval "sky launch t.yaml"',
            'echo "$(sky launch -y t.yaml)"', "echo `sky start mycluster`",
            'docker run --rm img sh -c "sky launch t.yaml"', "bash <<'EOF'\nsky launch t.yaml\nEOF",
            'python3 -c "import sky; sky.launch(task)"', "python -m sky launch t.yaml",
            "python3 - <<'PY'\nimport sky\nsky.launch(t)\nPY",
            f"bash {T}/launch.sh", f"{T}/launch.sh", f"python3 {T}/burst.py",
        ]),
        ("regression: bugs found while building", "deny", [
            # `-n` was once treated as a dry-run flag; az uses it for the resource name
            "az vm create -n x -g rg",
            # shebang-as-comment swallowed the whole script when lines were joined
            f"bash {T}/launch.sh",
            # comment ate its newline, merging a --dryrun line into a real launch
            "sky launch t.yaml # x\nsky launch --dryrun t2.yaml",
            # line continuation split the command across two segments
            "sky \\\n  launch t.yaml",
            # a quoted '#' is not a comment
            'echo "#" && sky launch t.yaml',
            "echo ${#arr[@]}; sky launch t.yaml",
            "sky launch t.yaml # we don't need --dryrun here",
            # a here-string (<<<) misread as a heredoc dropped every following line
            'cat <<< "x"\nsky launch t.yaml',
            # a quoted "<<EOF" misread as a heredoc did the same
            'echo "use <<EOF for heredocs"\nsky launch t.yaml',
            # an unterminated heredoc is not trusted as data
            "cat <<EOF\nsky launch t.yaml\n",
            # an UNQUOTED heredoc body is expanded by bash: its $(...) and `...` really run
            "cat <<EOF\n$(sky launch t.yaml)\nEOF",
            "cat > out.txt <<EOF\nresult: `sky start mycluster`\nEOF",
        ]),
        ("regression: found in production (the gate blocked its own PR)", "allow", [
            # exact shape of the PR command that was wrongly blocked: a QUOTED heredoc
            # inside $( ) inside double quotes, whose Markdown mentions a launch in backticks
            'gh pr create --title "x" --body "$(cat <<\'EOF\'\n'
            '**The design problem:** `git commit -m "notes"` must pass, `bash -c "sky launch"` must not.\n'
            'It follows `bash -c`, `eval`, `$(…)` and wrappers.\n'
            'EOF\n)" 2>&1',
            # quoted delimiters mean the body is literal -- nothing in it runs
            "cat <<'EOF'\n$(sky launch t.yaml)\nEOF",
            'cat <<"EOF"\n`sky launch t.yaml`\nEOF',
            "cat <<\\EOF\n$(sky launch t.yaml)\nEOF",
            # running this very test file: it mentions sky.launch( only inside strings
            f"python3 {os.path.abspath(__file__)} --help-not-real",
            # SDK names in Python strings and comments are text, not calls
            "python3 -c \"x = 'sky.launch(t)'; print(x)\"",
            "python3 - <<'PY'\n# later: sky.launch(task)\ndoc = 'call sky.launch(task) to start'\nprint(doc)\nPY",
        ]),
        ("python read with its parser, not a regex", "deny", [
            'python3 -c "import sky as s; s.launch(t)"',
            'python3 -c "from sky import launch; launch(t)"',
            'python3 -c "from sky import launch as go; go(t)"',
            "python3 -c \"import subprocess; subprocess.run(['sky', 'launch', 't.yaml'])\"",
            "python3 -c \"import os; os.system('cd /tmp && sky launch t.yaml')\"",
            "python3 -c \"import boto3; boto3.client('ec2').run_instances(ImageId='x', MinCount=1, MaxCount=1)\"",
            "python3 - <<'PY'\nimport runpod\nrunpod.create_pod(name='x', gpu_type_id='RTX 4090')\nPY",
        ]),
        ("must pass: normal work", "allow", [
            "ls -la", "echo hello | cat", 'python3 -c "print(1)"',
            "docker run --rm --gpus all nvidia/cuda:12.6.3-base-ubuntu24.04 nvidia-smi -L",
            "curl -fsS http://127.0.0.1:11434/api/version", "echo ${#arr[@]}",
        ]),
        ("must pass: spend words that are only text", "allow", [
            'git commit -m "add sky launch notes"', 'grep -rn "sky launch" build-log/',
            'echo "run sky launch to start a cluster"', 'cat <<< "sky launch is data here"',
            "git commit -q -F - <<'EOF'\nPhase 06b: spend gate\n\nsky launch is now blocked.\nsky jobs launch too.\nEOF",
            "cat > notes.md <<'EOF'\nsky launch -c gpu t.yaml\nEOF",
            "python3 - <<'PY'\ns = 'the map says sky launch --dryrun prints $/hr'\nprint(s)\nPY",
            "sky status # later we might: sky launch big.yaml",
        ]),
        ("must pass: read-only cloud commands", "allow", [
            "sky status", "sky check", "sky launch --dryrun task.yaml", "aws ec2 describe-instances",
            "gcloud compute instances list", "terraform plan", "pulumi preview", "modal --help",
            "dstack --version", f"bash {T}/harmless.sh", f"{T}/harmless.sh",
            f"bash {T}/apostrophe.sh", f"{T}/apostrophe.sh",
        ]),
    ]

    failures = 0
    for name, want, cases in groups:
        bad = [(c, got) for c in cases if (got := decision(c)) != want]
        failures += len(bad)
        print(f"{'ok  ' if not bad else 'FAIL'} {len(cases) - len(bad):3d}/{len(cases):<3d} {name} (expect {want})")
        for c, got in bad:
            print(f"        got {got}: {c!r}")
    print(f"\n{failures} failure(s)")
    return failures


if __name__ == "__main__":
    sys.exit(main())
