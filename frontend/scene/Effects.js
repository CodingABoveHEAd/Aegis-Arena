/**
 * Effects.js — Visually rich VFX: plasma bolt with trail + 4-part impact,
 * overcharge cannon with charge-up + heavy projectile, shield activation
 * with energy wisps, styled damage numbers, death debris, burn/slow visuals.
 *
 * r128 constraint: Box/Sphere/Cylinder/Torus/Cone/Octahedron/BufferGeometry only.
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
    /** @type {Array<{update:(dt:number,time:number)=>boolean}>} */
    this._active = [];
  }

  // ─── Per-frame ─────────────────────────────────────────────────────

  update(dt, time) {
    for (let i = this._active.length - 1; i >= 0; i--) {
      const done = this._active[i].update(dt, time);
      if (done) this._active.splice(i, 1);
    }
  }

  // ─── Plasma Bolt (BASIC_ATTACK) ───────────────────────────────────

  /**
   * Fires a glowing plasma bolt with a trailing particle ribbon.
   * On arrival: 4-part impact explosion (flash, ring, sparks, smoke).
   */
  projectile(from, to, color = 0x00d4ff, onHit) {
    const bolt = new THREE.Group();

    // Core sphere
    const coreMat = new THREE.MeshBasicMaterial({ color });
    const core = new THREE.Mesh(new THREE.SphereGeometry(0.06, 8, 6), coreMat);
    bolt.add(core);

    // Outer glow
    const glowMat = new THREE.MeshBasicMaterial({
      color, transparent: true, opacity: 0.35,
    });
    const glow = new THREE.Mesh(new THREE.SphereGeometry(0.12, 8, 6), glowMat);
    bolt.add(glow);

    bolt.position.copy(from);
    this.scene.add(bolt);

    const dir = new THREE.Vector3().subVectors(to, from);
    const dist = dir.length();
    dir.normalize();
    const speed = 10;
    let travelled = 0;

    // Trail particles
    const trailGeo = new THREE.SphereGeometry(0.02, 4, 3);
    const trailParticles = [];

    const self = this;
    this._active.push({
      update(dt) {
        travelled += speed * dt;
        const pos = from.clone().add(dir.clone().multiplyScalar(travelled));
        bolt.position.copy(pos);

        // Pulse glow
        glow.scale.setScalar(1 + 0.2 * Math.sin(travelled * 20));

        // Spawn trail particle every frame
        const tMat = new THREE.MeshBasicMaterial({
          color, transparent: true, opacity: 0.6,
        });
        const tp = new THREE.Mesh(trailGeo, tMat);
        tp.position.copy(pos);
        tp.userData._life = 0.3;
        tp.userData._maxLife = 0.3;
        self.scene.add(tp);
        trailParticles.push(tp);

        // Fade trail
        for (let i = trailParticles.length - 1; i >= 0; i--) {
          const p = trailParticles[i];
          p.userData._life -= dt;
          const t = p.userData._life / p.userData._maxLife;
          p.material.opacity = 0.6 * Math.max(0, t);
          p.scale.setScalar(Math.max(0.1, t));
          if (p.userData._life <= 0) {
            self.scene.remove(p);
            p.geometry.dispose();
            p.material.dispose();
            trailParticles.splice(i, 1);
          }
        }

        if (travelled >= dist) {
          // Cleanup bolt
          self.scene.remove(bolt);
          core.geometry.dispose(); core.material.dispose();
          glow.geometry.dispose(); glow.material.dispose();

          // Clean remaining trail
          for (const p of trailParticles) {
            self.scene.remove(p);
            p.geometry.dispose();
            p.material.dispose();
          }
          trailParticles.length = 0;

          // 4-part impact explosion
          self._impactExplosion(to, color);
          if (onHit) onHit();
          return true;
        }
        return false;
      },
    });
  }

  /**
   * 4-part impact: bright flash sphere, expanding ring, directional sparks, fading smoke puffs.
   */
  _impactExplosion(pos, color) {
    // 1. Flash sphere
    const flashMat = new THREE.MeshBasicMaterial({
      color: 0xffffff, transparent: true, opacity: 1.0,
    });
    const flash = new THREE.Mesh(new THREE.SphereGeometry(0.15, 8, 6), flashMat);
    flash.position.copy(pos);
    this.scene.add(flash);

    // 2. Expanding ring
    const ringMat = new THREE.MeshBasicMaterial({
      color, transparent: true, opacity: 0.8,
    });
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.03, 8, 24), ringMat);
    ring.position.copy(pos);
    ring.rotation.x = -Math.PI / 2;
    this.scene.add(ring);

    // 3. Sparks
    this._particleBurst(pos, color, 25, 3.5, 0.6);

    // 4. Smoke puffs
    const smokePuffs = [];
    const smokeGeo = new THREE.SphereGeometry(0.06, 6, 4);
    for (let i = 0; i < 6; i++) {
      const sMat = new THREE.MeshBasicMaterial({
        color: 0x444444, transparent: true, opacity: 0.4,
      });
      const puff = new THREE.Mesh(smokeGeo, sMat);
      puff.position.copy(pos);
      puff.userData._vel = new THREE.Vector3(
        (Math.random() - 0.5) * 1.5,
        Math.random() * 1.0 + 0.5,
        (Math.random() - 0.5) * 1.5,
      );
      this.scene.add(puff);
      smokePuffs.push(puff);
    }

    let elapsed = 0;
    const duration = 0.6;
    const self = this;
    this._active.push({
      update(dt) {
        elapsed += dt;
        const t = elapsed / duration;

        // Flash expand + fade
        flash.scale.setScalar(1 + t * 4);
        flashMat.opacity = Math.max(0, 1 - t * 2.5);

        // Ring expand + fade
        const rs = 1 + t * 12;
        ring.scale.set(rs, rs, 1);
        ringMat.opacity = 0.8 * (1 - t);

        // Smoke rise + fade
        for (const puff of smokePuffs) {
          puff.position.addScaledVector(puff.userData._vel, dt);
          puff.userData._vel.y -= 1.5 * dt;
          puff.material.opacity = 0.4 * (1 - t);
          puff.scale.setScalar(1 + t * 2);
        }

        if (t >= 1) {
          self.scene.remove(flash); flash.geometry.dispose(); flashMat.dispose();
          self.scene.remove(ring); ring.geometry.dispose(); ringMat.dispose();
          for (const puff of smokePuffs) {
            self.scene.remove(puff);
            puff.geometry.dispose();
            puff.material.dispose();
          }
          return true;
        }
        return false;
      },
    });
  }

  // ─── Shockwave / Overcharge Cannon (SPECIAL_SKILL) ────────────────

  /**
   * Expanding torus + heavy energy burst + camera shake.
   */
  shockwave(center, color = 0x00d4ff, cameraRig) {
    // Charge-up flash at center
    const chargeMat = new THREE.MeshBasicMaterial({
      color, transparent: true, opacity: 0.9,
    });
    const charge = new THREE.Mesh(new THREE.SphereGeometry(0.08, 8, 6), chargeMat);
    charge.position.copy(center);
    this.scene.add(charge);

    // Main shockwave ring
    const torusMat = new THREE.MeshBasicMaterial({
      color, transparent: true, opacity: 0.8,
    });
    const torus = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.04, 8, 32), torusMat);
    torus.rotation.x = -Math.PI / 2;
    torus.position.copy(center);
    this.scene.add(torus);

    // Secondary ring (slightly delayed)
    const ring2Mat = new THREE.MeshBasicMaterial({
      color: 0xffffff, transparent: true, opacity: 0.5,
    });
    const ring2 = new THREE.Mesh(new THREE.TorusGeometry(0.08, 0.02, 8, 24), ring2Mat);
    ring2.rotation.x = -Math.PI / 2;
    ring2.position.copy(center);
    this.scene.add(ring2);

    if (cameraRig) cameraRig.shake(0.15, 0.4);
    this._particleBurst(center, color, 40, 4.0, 0.8);

    let elapsed = 0;
    const duration = 0.9;
    const self = this;
    this._active.push({
      update(dt) {
        elapsed += dt;
        const t = elapsed / duration;

        // Charge-up grows then fades
        const chargeT = Math.min(t * 4, 1);
        charge.scale.setScalar(1 + chargeT * 3);
        chargeMat.opacity = 0.9 * (1 - chargeT);

        // Main ring expands
        const scale = 1 + t * 18;
        torus.scale.set(scale, scale, 1);
        torusMat.opacity = 0.8 * (1 - t);

        // Secondary ring (delayed)
        const t2 = Math.max(0, (t - 0.15) / 0.85);
        const scale2 = 1 + t2 * 14;
        ring2.scale.set(scale2, scale2, 1);
        ring2Mat.opacity = 0.5 * (1 - t2);

        if (t >= 1) {
          self.scene.remove(charge); charge.geometry.dispose(); chargeMat.dispose();
          self.scene.remove(torus); torus.geometry.dispose(); torusMat.dispose();
          self.scene.remove(ring2); ring2.geometry.dispose(); ring2Mat.dispose();
          return true;
        }
        return false;
      },
    });
  }

  // ─── Shield Activation (with energy wisps) ────────────────────────

  shieldPulse(center, color = 0x00d4ff) {
    // Expanding hex ring
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(0.3, 0.02, 8, 32),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.7 }),
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.copy(center);
    ring.position.y += 0.5;
    this.scene.add(ring);

    // Energy wisps — small spheres that spiral inward
    const wispGeo = new THREE.SphereGeometry(0.025, 4, 4);
    const wisps = [];
    for (let i = 0; i < 8; i++) {
      const angle = (i / 8) * Math.PI * 2;
      const wMat = new THREE.MeshBasicMaterial({
        color, transparent: true, opacity: 0.8,
      });
      const w = new THREE.Mesh(wispGeo, wMat);
      w.userData._angle = angle;
      w.userData._radius = 0.8;
      w.position.copy(center);
      w.position.y += 0.5;
      this.scene.add(w);
      wisps.push(w);
    }

    // Flash sphere
    const flashMat = new THREE.MeshBasicMaterial({
      color, transparent: true, opacity: 0.3,
    });
    const flashSphere = new THREE.Mesh(new THREE.SphereGeometry(0.35, 12, 8), flashMat);
    flashSphere.position.copy(center);
    flashSphere.position.y += 0.5;
    this.scene.add(flashSphere);

    let elapsed = 0;
    const duration = 0.7;
    const self = this;
    this._active.push({
      update(dt, time) {
        elapsed += dt;
        const t = elapsed / duration;

        // Ring expands
        const s = 1 + t * 3;
        ring.scale.set(s, s, 1);
        ring.material.opacity = 0.7 * (1 - t);

        // Wisps spiral inward
        for (const w of wisps) {
          w.userData._radius = 0.8 * (1 - t);
          w.userData._angle += dt * 8;
          const r = w.userData._radius;
          const a = w.userData._angle;
          w.position.set(
            center.x + Math.cos(a) * r,
            center.y + 0.5 + Math.sin(time * 6 + w.userData._angle) * 0.05,
            center.z + Math.sin(a) * r,
          );
          w.material.opacity = 0.8 * (1 - t);
          w.scale.setScalar(Math.max(0.1, 1 - t));
        }

        // Flash sphere elastic expand
        const elastic = 1 + 0.3 * Math.sin(t * Math.PI * 3) * (1 - t);
        flashSphere.scale.setScalar(elastic);
        flashMat.opacity = 0.3 * (1 - t);

        if (t >= 1) {
          self.scene.remove(ring); ring.geometry.dispose(); ring.material.dispose();
          self.scene.remove(flashSphere); flashSphere.geometry.dispose(); flashMat.dispose();
          for (const w of wisps) {
            self.scene.remove(w);
            w.geometry.dispose();
            w.material.dispose();
          }
          return true;
        }
        return false;
      },
    });
  }

  // ─── Damage Numbers (styled CSS2D) ────────────────────────────────

  damageNumber(pos, text, cssClass = 'damage-label') {
    const div = document.createElement('div');
    div.className = cssClass;
    div.textContent = text;
    // Add pop-in animation class
    div.style.animation = 'dmgPop 1.0s ease-out forwards';
    const label = new CSS2DObject(div);
    label.position.copy(pos);
    label.position.y += 1.2;
    this.scene.add(label);

    // Drift upward over lifetime
    const startY = label.position.y;
    let elapsed = 0;
    const lifetime = 1.2;
    const self = this;
    this._active.push({
      update(dt) {
        elapsed += dt;
        label.position.y = startY + elapsed * 0.8;
        if (elapsed >= lifetime) {
          self.scene.remove(label);
          div.remove();
          return true;
        }
        return false;
      },
    });
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

  // ─── Death effect ─────────────────────────────────────────────────

  deathEffect(pos, color = 0x00d4ff) {
    // Flash
    const flashMat = new THREE.MeshBasicMaterial({
      color: 0xffffff, transparent: true, opacity: 0.8,
    });
    const flash = new THREE.Mesh(new THREE.SphereGeometry(0.3, 8, 6), flashMat);
    flash.position.copy(pos);
    flash.position.y += 0.4;
    this.scene.add(flash);

    // Debris burst
    this._particleBurst(pos.clone().setY(pos.y + 0.4), color, 50, 4.0, 1.5);

    // Rising energy wisps
    const wispGeo = new THREE.SphereGeometry(0.03, 4, 4);
    const wisps = [];
    for (let i = 0; i < 8; i++) {
      const wMat = new THREE.MeshBasicMaterial({
        color, transparent: true, opacity: 0.7,
      });
      const w = new THREE.Mesh(wispGeo, wMat);
      w.position.copy(pos);
      w.position.y += 0.4;
      w.userData._vel = new THREE.Vector3(
        (Math.random() - 0.5) * 0.5,
        1.5 + Math.random() * 1.0,
        (Math.random() - 0.5) * 0.5,
      );
      this.scene.add(w);
      wisps.push(w);
    }

    let elapsed = 0;
    const duration = 1.5;
    const self = this;
    this._active.push({
      update(dt) {
        elapsed += dt;
        const t = elapsed / duration;

        flash.scale.setScalar(1 + t * 5);
        flashMat.opacity = 0.8 * (1 - t);

        for (const w of wisps) {
          w.position.addScaledVector(w.userData._vel, dt);
          w.material.opacity = 0.7 * (1 - t);
        }

        if (t >= 1) {
          self.scene.remove(flash); flash.geometry.dispose(); flashMat.dispose();
          for (const w of wisps) {
            self.scene.remove(w);
            w.geometry.dispose();
            w.material.dispose();
          }
          return true;
        }
        return false;
      },
    });
  }

  // ─── Burn visual — orbiting flame particles ───────────────────────

  burnVisual(agentGroup, duration = 2.0) {
    const particles = [];
    const geo = new THREE.SphereGeometry(0.03, 4, 4);
    for (let i = 0; i < 6; i++) {
      const mat = new THREE.MeshBasicMaterial({
        color: i % 2 === 0 ? 0xff6600 : 0xffaa00,
        transparent: true, opacity: 0.8,
      });
      const p = new THREE.Mesh(geo, mat);
      p.userData._angle = (i / 6) * Math.PI * 2;
      agentGroup.add(p);
      particles.push(p);
    }
    let elapsed = 0;
    this._active.push({
      update(dt, time) {
        elapsed += dt;
        for (const p of particles) {
          const a = p.userData._angle + time * 5;
          p.position.set(
            Math.cos(a) * 0.35,
            0.3 + Math.sin(time * 6 + p.userData._angle) * 0.15 + elapsed * 0.1,
            Math.sin(a) * 0.35,
          );
          p.material.opacity = 0.8 * (1 - elapsed / duration);
          p.scale.setScalar(0.8 + 0.4 * Math.sin(time * 8 + p.userData._angle));
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

    // Ice crystal particles
    const crystalGeo = new THREE.OctahedronGeometry(0.025);
    const crystals = [];
    for (let i = 0; i < 5; i++) {
      const cMat = new THREE.MeshBasicMaterial({
        color: 0x88ccff, transparent: true, opacity: 0.6,
      });
      const c = new THREE.Mesh(crystalGeo, cMat);
      const angle = (i / 5) * Math.PI * 2;
      c.position.set(
        pos.x + Math.cos(angle) * 0.25,
        pos.y + 0.3,
        pos.z + Math.sin(angle) * 0.25,
      );
      c.userData._vel = new THREE.Vector3(0, 0.5, 0);
      this.scene.add(c);
      crystals.push(c);
    }

    let elapsed = 0;
    const duration = 0.5;
    const self = this;
    this._active.push({
      update(dt) {
        elapsed += dt;
        const t = elapsed / duration;
        ring.scale.set(1 + t * 2, 1 + t * 2, 1);
        ring.material.opacity = 0.7 * (1 - t);

        for (const c of crystals) {
          c.position.addScaledVector(c.userData._vel, dt);
          c.material.opacity = 0.6 * (1 - t);
          c.rotation.y += dt * 3;
        }

        if (t >= 1) {
          self.scene.remove(ring);
          ring.geometry.dispose();
          ring.material.dispose();
          for (const c of crystals) {
            self.scene.remove(c);
            c.geometry.dispose();
            c.material.dispose();
          }
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
          p.mesh.scale.setScalar(Math.max(0.1, 1 - t * 0.5));
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
