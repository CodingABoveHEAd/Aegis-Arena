/**
 * Effects.js — Visual effects: projectile, shockwave, shield pulse,
 * damage numbers, tile glow, death debris, burn visual, slow visual.
 */

import * as THREE from 'three';
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js';

export class Effects {
  /**
   * @param {THREE.Scene} scene
   * @param {CSS2DRenderer} labelRenderer
   */
  constructor(scene, labelRenderer) {
    this.scene = scene;
    this.labelRenderer = labelRenderer;
    /** @type {Array<{update:(dt:number,time:number)=>boolean}>} active effects */
    this._active = [];
  }

  // ─── Per-frame ─────────────────────────────────────────────────────

  update(dt, time) {
    // Update each effect; remove when it returns true (done).
    for (let i = this._active.length - 1; i >= 0; i--) {
      const done = this._active[i].update(dt, time);
      if (done) {
        this._active.splice(i, 1);
      }
    }
  }

  // ─── Projectile (attack) ──────────────────────────────────────────

  /**
   * Fire a glowing sphere that travels from `from` to `to` and explodes.
   * @param {THREE.Vector3} from
   * @param {THREE.Vector3} to
   * @param {number} color
   * @param {Function} [onHit] — callback on arrival.
   */
  projectile(from, to, color = 0x00d4ff, onHit) {
    const sphere = new THREE.Mesh(
      new THREE.SphereGeometry(0.06, 8, 6),
      new THREE.MeshBasicMaterial({ color }),
    );
    sphere.position.copy(from);
    this.scene.add(sphere);

    const dir = new THREE.Vector3().subVectors(to, from);
    const dist = dir.length();
    dir.normalize();
    const speed = 8;
    let travelled = 0;

    const self = this;
    this._active.push({
      update(dt) {
        travelled += speed * dt;
        sphere.position.copy(from.clone().add(dir.clone().multiplyScalar(travelled)));
        if (travelled >= dist) {
          self.scene.remove(sphere);
          sphere.geometry.dispose();
          sphere.material.dispose();
          self._particleBurst(to, color, 20);
          if (onHit) onHit();
          return true;
        }
        return false;
      },
    });
  }

  // ─── Shockwave (skill: shockwave) ─────────────────────────────────

  /**
   * Expanding torus + particles + optional camera shake.
   */
  shockwave(center, color = 0x00d4ff, cameraRig) {
    const torus = new THREE.Mesh(
      new THREE.TorusGeometry(0.1, 0.03, 8, 32),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.8 }),
    );
    torus.rotation.x = -Math.PI / 2;
    torus.position.copy(center);
    this.scene.add(torus);

    if (cameraRig) cameraRig.shake(0.12, 0.35);
    this._particleBurst(center, color, 30);

    let elapsed = 0;
    const duration = 0.7;
    const self = this;
    this._active.push({
      update(dt) {
        elapsed += dt;
        const t = elapsed / duration;
        const scale = 1 + t * 15;
        torus.scale.set(scale, scale, 1);
        torus.material.opacity = 0.8 * (1 - t);
        if (t >= 1) {
          self.scene.remove(torus);
          torus.geometry.dispose();
          torus.material.dispose();
          return true;
        }
        return false;
      },
    });
  }

  // ─── Shield pulse ─────────────────────────────────────────────────

  shieldPulse(center, color = 0x00d4ff) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.3, 0.02, 8, 32),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.7 }),
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.copy(center);
    ring.position.y += 0.6;
    this.scene.add(ring);

    let elapsed = 0;
    const duration = 0.5;
    const self = this;
    this._active.push({
      update(dt) {
        elapsed += dt;
        const t = elapsed / duration;
        const s = 1 + t * 3;
        ring.scale.set(s, s, 1);
        ring.material.opacity = 0.7 * (1 - t);
        if (t >= 1) {
          self.scene.remove(ring);
          ring.geometry.dispose();
          ring.material.dispose();
          return true;
        }
        return false;
      },
    });
  }

  // ─── Damage numbers (CSS2D) ────────────────────────────────────────

  /**
   * Show a floating damage number at a world position.
   * @param {THREE.Vector3} pos
   * @param {number|string} text
   * @param {string} cssClass — e.g. 'damage-label'
   */
  damageNumber(pos, text, cssClass = 'damage-label') {
    const div = document.createElement('div');
    div.className = cssClass;
    div.textContent = text;
    const label = new CSS2DObject(div);
    label.position.copy(pos);
    label.position.y += 1.2;
    this.scene.add(label);

    // Remove after animation
    setTimeout(() => {
      this.scene.remove(label);
      div.remove();
    }, 1200);
  }

  // ─── Tile glow pulse ──────────────────────────────────────────────

  tileGlow(tileMesh, color = 0x00d4ff, duration = 0.6) {
    if (!tileMesh) return;
    const origEmissive = tileMesh.material.emissive.getHex();
    const origIntensity = tileMesh.material.emissiveIntensity;
    tileMesh.material.emissive.set(color);
    tileMesh.material.emissiveIntensity = 1.0;

    let elapsed = 0;
    this._active.push({
      update(dt) {
        elapsed += dt;
        const t = elapsed / duration;
        tileMesh.material.emissiveIntensity = 1.0 * (1 - t) + origIntensity * t;
        if (t >= 1) {
          tileMesh.material.emissive.set(origEmissive);
          tileMesh.material.emissiveIntensity = origIntensity;
          return true;
        }
        return false;
      },
    });
  }

  // ─── Death effect (debris particles) ──────────────────────────────

  deathEffect(pos, color = 0x00d4ff) {
    this._particleBurst(pos, color, 40, 3.0, 1.5);
  }

  // ─── Burn visual — orbiting flame particles ───────────────────────

  /**
   * Creates small orange flame particles that orbit an agent.
   * @param {THREE.Group} agentGroup
   * @param {number} duration — seconds to show.
   */
  burnVisual(agentGroup, duration = 2.0) {
    const particles = [];
    const geo = new THREE.SphereGeometry(0.03, 4, 4);
    for (let i = 0; i < 5; i++) {
      const mat = new THREE.MeshBasicMaterial({ color: 0xff6600, transparent: true, opacity: 0.8 });
      const p = new THREE.Mesh(geo, mat);
      p.userData._angle = (i / 5) * Math.PI * 2;
      agentGroup.add(p);
      particles.push(p);
    }
    let elapsed = 0;
    this._active.push({
      update(dt, time) {
        elapsed += dt;
        for (const p of particles) {
          const a = p.userData._angle + time * 4;
          p.position.set(Math.cos(a) * 0.35, 0.5 + Math.sin(time * 6 + p.userData._angle) * 0.1, Math.sin(a) * 0.35);
          p.material.opacity = 0.8 * (1 - elapsed / duration);
        }
        if (elapsed >= duration) {
          for (const p of particles) {
            agentGroup.remove(p);
            p.geometry.dispose();
            p.material.dispose();
          }
          return true;
        }
        return false;
      },
    });
  }

  // ─── Slow visual — blue ring flash ────────────────────────────────

  slowVisual(pos) {
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.3, 0.03, 8, 32),
      new THREE.MeshBasicMaterial({ color: 0x0066ff, transparent: true, opacity: 0.7 }),
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.copy(pos);
    ring.position.y += 0.1;
    this.scene.add(ring);

    let elapsed = 0;
    const duration = 0.4;
    const self = this;
    this._active.push({
      update(dt) {
        elapsed += dt;
        const t = elapsed / duration;
        ring.scale.set(1 + t * 2, 1 + t * 2, 1);
        ring.material.opacity = 0.7 * (1 - t);
        if (t >= 1) {
          self.scene.remove(ring);
          ring.geometry.dispose();
          ring.material.dispose();
          return true;
        }
        return false;
      },
    });
  }

  // ─── Internal: particle burst helper ──────────────────────────────

  _particleBurst(origin, color, count = 20, speed = 2.0, lifetime = 0.7) {
    const geo = new THREE.SphereGeometry(0.025, 4, 3);
    const particles = [];
    for (let i = 0; i < count; i++) {
      const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 1 });
      const p = new THREE.Mesh(geo, mat);
      p.position.copy(origin);
      const vel = new THREE.Vector3(
        (Math.random() - 0.5) * speed,
        Math.random() * speed * 0.8,
        (Math.random() - 0.5) * speed,
      );
      this.scene.add(p);
      particles.push({ mesh: p, vel });
    }

    let elapsed = 0;
    const self = this;
    this._active.push({
      update(dt) {
        elapsed += dt;
        const t = elapsed / lifetime;
        for (const p of particles) {
          p.vel.y -= 4.0 * dt; // gravity
          p.mesh.position.addScaledVector(p.vel, dt);
          p.mesh.material.opacity = Math.max(0, 1 - t);
        }
        if (t >= 1) {
          for (const p of particles) {
            self.scene.remove(p.mesh);
            p.mesh.geometry.dispose();
            p.mesh.material.dispose();
          }
          return true;
        }
        return false;
      },
    });
  }
}
