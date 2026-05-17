from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
VENDOR = ROOT / "frontend/static/js/three/vendor"

def test_postprocessing_dependency_closure_vendored():
    pp = VENDOR / "postprocessing"
    sh = VENDOR / "shaders"
    for f in ("EffectComposer", "Pass", "RenderPass", "ShaderPass",
              "MaskPass", "UnrealBloomPass", "OutputPass"):
        assert (pp / f"{f}.js").is_file(), f"missing postprocessing/{f}.js"
    for f in ("CopyShader", "LuminosityHighPassShader", "OutputShader"):
        assert (sh / f"{f}.js").is_file(), f"missing shaders/{f}.js"

def test_importmap_has_postprocessing_entries():
    html = (ROOT / "frontend/templates/index.html").read_text(encoding="utf-8")
    for spec in ("three/addons/postprocessing/EffectComposer.js",
                 "three/addons/postprocessing/RenderPass.js",
                 "three/addons/postprocessing/UnrealBloomPass.js",
                 "three/addons/postprocessing/OutputPass.js",
                 "three/addons/shaders/CopyShader.js"):
        assert spec in html, f"importmap missing {spec}"

def test_style_css_immersive_scope_and_responsive():
    css = (ROOT / "frontend/static/css/style.css").read_text(encoding="utf-8")
    assert ".twin-immersive" in css
    assert "#three-stage" in css
    assert "@media" in css and "960px" in css
    assert "backdrop-filter" in css
