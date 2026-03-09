/**
 * AgentMesh.js — 3D agent character with body parts, shields, HP/energy bars,
 * idle animation, movement lerp, hit reaction, and low-HP flicker.
 *
 * r128 constraint: no CapsuleGeometry — use CylinderGeometry for torso/legs.
 */

import * as THREE from 'three';

const AGENT_COLORS = {
  1: { primary: 0x00d4ff, dark: 0x004466, visor: 0x00ffff },
  2: { primary: 0xff3333, dark: 0x660000, visor: 0xff6666 },
};

export class AgentMesh {
  /**
   * @param {THREE.Scene} scene
   * @param {number} agentId — 1 or 2.
   */
  constructor(scene, agentId) {
    this.scene = scene;
    this.agentId = agentId;
    this.colors = AGENT_COLORS[agentId];
    this.group = new THREE.Group();
    this.group.name = `agent_${agentId}`;

    // State
    this._targetPos = new THREE.Vector3();
    this._currentPos = new THREE.Vector3();
    this._idleTime = Math.random() * 100;
    this._hitReactionTimer = 0;
    this._hitDir = new THREE.Vector3();
    this._lowHpFlicker = false;
    this._shieldVisible = false;

    this._build();
    scene.add(this.group);
  }

  // ─── Build body ────────────────────────────────────────────────────

  _build() {
    const C = this.colors;

    // Torso (cylinder, r128 safe)
    const torsoGeo = new THREE.CylinderGeometry(0.16, 0.14, 0.45, 8);
    this.torso = new THREE.Mesh(torsoGeo, new THREE.MeshStandardMaterial({
      color: C.dark, metalness: 0.6, roughness: 0.4,
    }));
    this.torso.position.y = 0.55;
    this.torso.castShadow = true;
    this.group.add(this.torso);

    // Head
    const headGeo = new THREE.SphereGeometry(0.14, 16, 12);
    this.head = new THREE.Mesh(headGeo, new THREE.MeshStandardMaterial({
      color: C.dark, metalness: 0.5, roughness: 0.3,
    }));
    this.head.position.y = 0.92;
    this.head.castShadow = true;
    this.group.add(this.head);

    // Visor
    const visorGeo = new THREE.BoxGeometry(0.24, 0.06, 0.06);
    this.visor = new THREE.Mesh(visorGeo, new THREE.MeshStandardMaterial({
      color: C.visor, emissive: C.visor, emissiveIntensity: 1.0,
      metalness: 0.8, roughness: 0.2,
    }));
    this.visor.position.set(0, 0.93, 0.12);
    this.group.add(this.visor);

    // Shoulders
    const shoulderGeo = new THREE.SphereGeometry(0.07, 8, 6);
    const shoulderMat = new THREE.MeshStandardMaterial({
      color: C.primary, emissive: C.primary, emissiveIntensity: 0.3,
      metalness: 0.6, roughness: 0.3,
    });
    this.shoulderL = new THREE.Mesh(shoulderGeo, shoulderMat);
    this.shoulderL.position.set(-0.22, 0.72, 0);
    this.group.add(this.shoulderL);
    this.shoulderR = new THREE.Mesh(shoulderGeo, shoulderMat.clone());
    this.shoulderR.position.set(0.22, 0.72, 0);
    this.group.add(this.shoulderR);

    // Legs
    const legGeo = new THREE.CylinderGeometry(0.05, 0.06, 0.25, 6);
    const legMat = new THREE.MeshStandardMaterial({ color: C.dark, metalness: 0.4, roughness: 0.5 });
    this.legL = new THREE.Mesh(legGeo, legMat);
    this.legL.position.set(-0.08, 0.2, 0);
    this.legL.castShadow = true;
    this.group.add(this.legL);
    this.legR = new THREE.Mesh(legGeo, legMat.clone());
    this.legR.position.set(0.08, 0.2, 0);
    this.legR.castShadow = true;
    this.group.add(this.legR);

    // Feet
    const footGeo = new THREE.BoxGeometry(0.08, 0.04, 0.14);
    const footMat = new THREE.MeshStandardMaterial({ color: C.dark, metalness: 0.3, roughness: 0.6 });
    this.footL = new THREE.Mesh(footGeo, footMat);
    this.footL.position.set(-0.08, 0.05, 0.02);
    this.group.add(this.footL);
    this.footR = new THREE.Mesh(footGeo, footMat.clone());
    this.footR.position.set(0.08, 0.05, 0.02);
    this.group.add(this.footR);

    // Base glow ring
    const ringGeo = new THREE.TorusGeometry(0.22, 0.02, 8, 32);
    this.baseRing = new THREE.Mesh(ringGeo, new THREE.MeshStandardMaterial({
      color: C.primary, emissive: C.primary, emissiveIntensity: 0.8,
      transparent: true, opacity: 0.7,
    }));
    this.baseRing.rotation.x = -Math.PI / 2;
    this.baseRing.position.y = 0.02;
    this.group.add(this.baseRing);

    // Shield sphere (initially hidden)
    this.shield = new THREE.Mesh(
      new THREE.SphereGeometry(0.45, 16, 12),
      new THREE.MeshStandardMaterial({
        color: C.primary, emissive: C.primary, emissiveIntensity: 0.4,
        transparent: true, opacity: 0.25, side: THREE.DoubleSide,
      }),
    );
    this.shield.position.y = 0.55;
    this.shield.visible = false;
    this.group.add(this.shield);

    // HP bar (green → red)
    this._hpBarBg = this._makeBar(0.4, 0x222222, 1.12);
    this._hpBarFill = this._makeBar(0.4, 0x00ff44, 1.12);
    this.group.add(this._hpBarBg);
    this.group.add(this._hpBarFill);

    // Energy bar (yellow)
    this._enBarBg = this._makeBar(0.32, 0x222222, 1.04);
    this._enBarFill = this._makeBar(0.32, 0xffaa00, 1.04);
    this.group.add(this._enBarBg);
    this.group.add(this._enBarFill);
  }

  _makeBar(width, color, y) {
    const geo = new THREE.BoxGeometry(width, 0.035, 0.035);
    const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.85 });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.y = y;
    return mesh;
  }

  // ─── Public API ────────────────────────────────────────────────────

  /**
   * Set initial world position instantly (no lerp).
   */
  setPosition(worldPos) {
    this._targetPos.copy(worldPos);
    this._currentPos.copy(worldPos);
    this.group.position.copy(worldPos);
  }

  /**
   * Set new target for smooth lerp movement.
   */
  moveTo(worldPos) {
    this._targetPos.copy(worldPos);
  }

  /**
   * Face towards a world point.
   */
  lookAt(worldPos) {
    const dir = new THREE.Vector3().subVectors(worldPos, this.group.position);
    dir.y = 0;
    if (dir.lengthSq() > 0.001) {
      this.group.lookAt(this.group.position.clone().add(dir));
    }
  }

  /**
   * Update HP bar fill (0–1 fraction).
   */
  setHP(fraction) {
    this._hpBarFill.scale.x = Math.max(0.01, fraction);
    this._hpBarFill.position.x = -(0.2 * (1 - fraction));
    // Color: green → yellow → red
    const r = fraction < 0.5 ? 1 : 1 - (fraction - 0.5) * 2;
    const g = fraction > 0.5 ? 1 : fraction * 2;
    this._hpBarFill.material.color.setRGB(r, g, 0);
    this._lowHpFlicker = fraction < 0.3;
  }

  /**
   * Update energy bar fill (0–1 fraction).
   */
  setEnergy(fraction) {
    this._enBarFill.scale.x = Math.max(0.01, fraction);
    this._enBarFill.position.x = -(0.16 * (1 - fraction));
  }

  /**
   * Show/hide shield.
   */
  setShield(active) {
    this._shieldVisible = active;
    this.shield.visible = active;
  }

  /**
   * Trigger a brief hit reaction towards the given direction.
   */
  applyHitReaction(direction) {
    this._hitDir.copy(direction).normalize().multiplyScalar(0.15);
    this._hitReactionTimer = 0.25;
  }

  /**
   * Make the mesh invisible.
   */
  hide() {
    this.group.visible = false;
  }

  show() {
    this.group.visible = true;
  }

  // ─── Per-frame animation ───────────────────────────────────────────

  update(dt, time) {
    this._idleTime += dt;

    // Smooth movement lerp
    const lerpSpeed = 8.0;
    this._currentPos.lerp(this._targetPos, 1 - Math.exp(-lerpSpeed * dt));
    this.group.position.copy(this._currentPos);

    // Hit reaction
    if (this._hitReactionTimer > 0) {
      this._hitReactionTimer -= dt;
      const t = Math.max(0, this._hitReactionTimer) / 0.25;
      const offset = this._hitDir.clone().multiplyScalar(Math.sin(t * Math.PI));
      this.group.position.add(offset);
    }

    // Idle bob
    const bob = Math.sin(this._idleTime * 2.5) * 0.02;
    this.torso.position.y = 0.55 + bob;
    this.head.position.y = 0.92 + bob;
    this.visor.position.y = 0.93 + bob;
    this.shoulderL.position.y = 0.72 + bob;
    this.shoulderR.position.y = 0.72 + bob;

    // Low-HP flicker
    if (this._lowHpFlicker) {
      const flicker = Math.sin(time * 15) > 0.3 ? 1 : 0.3;
      this.visor.material.emissiveIntensity = flicker;
    } else {
      this.visor.material.emissiveIntensity = 1.0;
    }

    // Shield pulse
    if (this._shieldVisible) {
      this.shield.material.opacity = 0.15 + 0.1 * Math.sin(time * 4);
    }

    // Base ring pulse
    this.baseRing.material.emissiveIntensity = 0.5 + 0.3 * Math.sin(time * 2);
  }
}
