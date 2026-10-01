from pathlib import Path


def test_dashboard_uses_safe_dom_rendering_for_api_data():
    dashboard = (Path(__file__).parents[1] / "frontend" / "dashboard.html").read_text(encoding="utf-8")

    assert "createElement(" in dashboard
    assert ".textContent" in dashboard
    assert ".replaceChildren()" in dashboard


def test_dashboard_does_not_use_html_injection_sinks():
    dashboard = (Path(__file__).parents[1] / "frontend" / "dashboard.html").read_text(encoding="utf-8")

    forbidden_sinks = (
        ".innerHTML",
        ".outerHTML",
        "insertAdjacentHTML(",
        "document.write(",
    )
    for sink in forbidden_sinks:
        assert sink not in dashboard
