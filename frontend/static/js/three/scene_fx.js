// scene_fx.js — 后处理：Bloom + ACESFilmic。失败只关后处理，不触发 .three-fallback。
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

export class SceneFX {
  constructor() {
    this.enabled = false;
    this.composer = null;
    this._renderer = null;
    this._scene = null;
    this._camera = null;
  }

  // 装配；任何失败 → enabled=false（调用方回落 renderer.render(scene,camera)）。
  mount(renderer, scene, camera) {
    this._renderer = renderer; this._scene = scene; this._camera = camera;
    try {
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.05;
      const size = renderer.getSize(new THREE.Vector2());
      const composer = new EffectComposer(renderer);
      composer.addPass(new RenderPass(scene, camera));
      const bloom = new UnrealBloomPass(
        new THREE.Vector2(Math.max(1, size.x), Math.max(1, size.y)),
        0.65,   // strength（保守，仅提亮高 emissive）
        0.4,    // radius
        0.85    // threshold（仅窗口/流线/交通核等高亮溢出）
      );
      composer.addPass(bloom);
      composer.addPass(new OutputPass());
      this.composer = composer;
      this.enabled = true;
    } catch (err) {
      this.enabled = false;
      this.composer = null;
    }
  }

  setSize(w, h) {
    if (this.enabled && this.composer) {
      try { this.composer.setSize(w, h); } catch (e) { this.enabled = false; }
    }
  }

  // 由 RAF 调用：enabled 走 composer，否则回落基础渲染（仍 3D，无辉光）。
  render() {
    if (this.enabled && this.composer) {
      try { this.composer.render(); return; } catch (e) { this.enabled = false; }
    }
    if (this._renderer && this._scene && this._camera) {
      this._renderer.render(this._scene, this._camera);
    }
  }

  dispose() {
    try { this.composer?.dispose?.(); } catch (e) { /* noop */ }
    this.composer = null; this.enabled = false;
    this._renderer = this._scene = this._camera = null;
  }
}
