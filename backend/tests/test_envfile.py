from airday import envfile


def test_parse_skips_comments_blanks_and_strips_quotes(tmp_path):
    p = tmp_path / ".env"
    p.write_text('# comment\n\nA=1\nexport B="two words"\nC=\'x=y\'\nEMPTY=\nnoequals\n', encoding="utf-8")
    assert envfile.parse(str(p)) == {"A": "1", "B": "two words", "C": "x=y", "EMPTY": ""}


def test_load_skips_empty_values_and_keeps_existing_env(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text("KEEP=file\nNEW=file\nEMPTY=\n", encoding="utf-8")
    monkeypatch.setenv("KEEP", "env")
    monkeypatch.delenv("NEW", raising=False)
    monkeypatch.delenv("EMPTY", raising=False)
    envfile.load(str(p))
    import os
    assert os.environ["KEEP"] == "env" and os.environ["NEW"] == "file" and "EMPTY" not in os.environ


def test_set_value_replaces_or_appends(tmp_path):
    p = tmp_path / ".env"
    p.write_text("A=1\nB=2\n", encoding="utf-8")
    envfile.set_value(str(p), "A", "9")
    envfile.set_value(str(p), "C", "3")
    assert envfile.parse(str(p)) == {"A": "9", "B": "2", "C": "3"}
