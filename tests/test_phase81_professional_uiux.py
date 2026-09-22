from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_professional_theme_has_core_visual_tokens():
    from ui.theme import PALETTE, FONT
    for key in ("bg", "surface", "border", "text", "primary", "success", "danger", "nav"):
        assert key in PALETTE and PALETTE[key]
    assert FONT == "Segoe UI"


def test_pos_uses_central_palette_and_professional_font():
    text = (ROOT / "ui" / "pos.py").read_text(encoding="utf-8")
    assert 'UI_BG = PALETTE["bg"]' in text
    assert 'HEADER_COLOR = PALETTE["nav"]' in text
    assert 'font=("Segoe UI"' in text


def test_dashboard_gold_identity_is_not_stale():
    text = (ROOT / "professional_dashboard.py").read_text(encoding="utf-8")
    assert "BKPOS 10.0.0" in text
    assert "Ver 20 JAN 2026" not in text
