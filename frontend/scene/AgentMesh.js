/**
 * AgentMesh.js — Professional armored warrior agents with weapons,
 * detailed body segments, idle animation, hit reaction, low-HP effects.
 *
 * r128 constraint: no CapsuleGeometry, no GLTFLoader.
 * All geometry from Box / Sphere / Cylinder / Torus / Cone / Octahedron / BufferGeometry.
 */

import * as THREE from 'three';

const AGENT_COLORS = {
  1: {
    primary: 0x00d4ff, dark: 0x003855, accent: 0x00ffff,
    armor: 0x1a3a50, trim: 0x00bbee, visor: 0x00ffff,
  },
  2: {
    primary: 0xff3333, dark: 0x551111, accent: 0xff6666,
    armor: 0x4a1a1a, trim: 0xee3333, visor: 0xff6666,
  },
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

    // --- Materials ---
    const armorMat = new THREE.MeshStandardMaterial({
      color: C.armor, metalness: 0.7, roughness: 0.3,
    });
    const darkMat = new THREE.MeshStandardMaterial({
      color: C.dark, metalness: 0.5, roughness: 0.4,
    });
    const trimMat = new THREE.MeshStandardMaterial({
      color: C.trim, emissive: C.trim, emissiveIntensity: 0.4,
      metalness: 0.8, roughness: 0.2,
    });
    const accentMat = new THREE.MeshStandardMaterial({
      color: C.accent, emissive: C.accent, emissiveIntensity: 0.6,
      metalness: 0.6, roughness: 0.2,
    });

    // ─── Legs ────────────────────────────────────────────────
    // Upper legs (thigh armor)
    const thighGeo = new THREE.CylinderGeometry(0.065, 0.055, 0.18, 8);
    this.thighL = new THREE.Mesh(thighGeo, armorMat);
    this.thighL.position.set(-0.08, 0.24, 0);
    this.thighL.castShadow = true;
    this.group.add(this.thighL);

    this.thighR = new THREE.Mesh(thighGeo, armorMat.clone());
    this.thighR.position.set(0.08, 0.24, 0);
    this.thighR.castShadow = true;
    this.group.add(this.thighR);

    // Lower legs (shin guards)
    const shinGeo = new THREE.CylinderGeometry(0.05, 0.06, 0.16, 8);
    this.shinL = new THREE.Mesh(shinGeo, darkMat);
    this.shinL.position.set(-0.08, 0.1, 0);
    this.shinL.castShadow = true;
    this.group.add(this.shinL);

    this.shinR = new THREE.Mesh(shinGeo, darkMat.clone());
    this.shinR.position.set(0.08, 0.1, 0);
    this.shinR.castShadow = true;
    this.group.add(this.shinR);

    // Knee guards
    const kneeGeo = new THREE.SphereGeometry(0.04, 8, 6);
    this.kneeL = new THREE.Mesh(kneeGeo, trimMat);
    this.kneeL.position.set(-0.08, 0.16, 0.03);
    this.group.add(this.kneeL);
    this.kneeR = new THREE.Mesh(kneeGeo, trimMat.clone());
    this.kneeR.position.set(0.08, 0.16, 0.03);
    this.group.add(this.kneeR);

    // Feet (armored boots)
    const footGeo = new THREE.BoxGeometry(0.08, 0.04, 0.14);
    const footMat = new THREE.MeshStandardMaterial({ color: C.dark, metalness: 0.5, roughness: 0.4 });
    this.footL = new THREE.Mesh(footGeo, footMat);
    this.footL.position.set(-0.08, 0.04, 0.02);
    this.group.add(this.footL);
    this.footR = new THREE.Mesh(footGeo, footMat.clone());
    this.footR.position.set(0.08, 0.04, 0.02);
    this.group.add(this.footR);

    // ─── Torso ───────────────────────────────────────────────
    // Core torso (chest plate)
    const torsoGeo = new THREE.CylinderGeometry(0.17, 0.13, 0.28, 8);
    this.torso = new THREE.Mesh(torsoGeo, armorMat.clone());
    this.torso.position.y = 0.48;
    this.torso.castShadow = true;
    this.group.add(this.torso);

    // Chest detail (front plate)
    const chestPlateGeo = new THREE.BoxGeometry(0.22, 0.16, 0.06);
    this.chestPlate = new THREE.Mesh(chestPlateGeo, new THREE.MeshStandardMaterial({
      color: C.armor, metalness: 0.8, roughness: 0.2,
    }));
    this.chestPlate.position.set(0, 0.50, 0.11);
    this.group.add(this.chestPlate);

    // Center core (glowing energy core on chest)
    const coreGeo = new THREE.SphereGeometry(0.04, 8, 6);
    this.core = new THREE.Mesh(coreGeo, accentMat.clone());
    this.core.position.set(0, 0.50, 0.15);
    this.group.add(this.core);

    // Waist / belt
    const waistGeo = new THREE.CylinderGeometry(0.14, 0.12, 0.06, 8);
    this.waist = new THREE.Mesh(waistGeo, darkMat.clone());
    this.waist.position.y = 0.35;
    this.group.add(this.waist);

    // Belt buckle (trim)
    const buckleGeo = new THREE.BoxGeometry(0.08, 0.04, 0.04);
    this.buckle = new THREE.Mesh(buckleGeo, trimMat.clone());
    this.buckle.position.set(0, 0.35, 0.11);
    this.group.add(this.buckle);

    // ─── Shoulders + Arms ────────────────────────────────────
    // Shoulder pads (large, layered)
    const shoulderGeo = new THREE.SphereGeometry(0.09, 8, 6);
    this.shoulderL = new THREE.Mesh(shoulderGeo, armorMat.clone());
    this.shoulderL.position.set(-0.24, 0.58, 0);
    this.shoulderL.scale.set(1, 0.8, 1);
    this.group.add(this.shoulderL);

    this.shoulderR = new THREE.Mesh(shoulderGeo, armorMat.clone());
    this.shoulderR.position.set(0.24, 0.58, 0);
    this.shoulderR.scale.set(1, 0.8, 1);
    this.group.add(this.shoulderR);

    // Shoulder trim rings
    const shoulderRingGeo = new THREE.TorusGeometry(0.08, 0.012, 6, 16);
    const sRingL = new THREE.Mesh(shoulderRingGeo, trimMat.clone());
    sRingL.position.set(-0.24, 0.58, 0);
    sRingL.rotation.x = Math.PI / 2;
    this.group.add(sRingL);
    const sRingR = new THREE.Mesh(shoulderRingGeo, trimMat.clone());
    sRingR.position.set(0.24, 0.58, 0);
    sRingR.rotation.x = Math.PI / 2;
    this.group.add(sRingR);

    // Upper arms
    const upperArmGeo = new THREE.CylinderGeometry(0.04, 0.035, 0.14, 6);
    this.upperArmL = new THREE.Mesh(upperArmGeo, darkMat.clone());
    this.upperArmL.position.set(-0.24, 0.46, 0);
    this.group.add(this.upperArmL);
    this.upperArmR = new THREE.Mesh(upperArmGeo, darkMat.clone());
    this.upperArmR.position.set(0.24, 0.46, 0);
    this.group.add(this.upperArmR);

    // Forearms (gauntlets)
    const forearmGeo = new THREE.CylinderGeometry(0.045, 0.04, 0.12, 6);
    this.forearmL = new THREE.Mesh(forearmGeo, armorMat.clone());
    this.forearmL.position.set(-0.24, 0.35, 0);
    this.group.add(this.forearmL);
    this.forearmR = new THREE.Mesh(forearmGeo, armorMat.clone());
    this.forearmR.position.set(0.24, 0.35, 0);
    this.group.add(this.forearmR);

    // ─── Head / Helmet ───────────────────────────────────────
    // Helmet base (sphere)
    const helmetGeo = new THREE.SphereGeometry(0.13, 16, 12);
    this.head = new THREE.Mesh(helmetGeo, armorMat.clone());
    this.head.position.y = 0.72;
    this.head.castShadow = true;
    this.group.add(this.head);

    // Helmet crest / ridge
    const crestGeo = new THREE.BoxGeometry(0.03, 0.08, 0.20);
    this.crest = new THREE.Mesh(crestGeo, trimMat.clone());
    this.crest.position.set(0, 0.80, -0.02);
    this.group.add(this.crest);

    // Visor (glowing slit)
    const visorGeo = new THREE.BoxGeometry(0.22, 0.04, 0.04);
    this.visor = new THREE.Mesh(visorGeo, new THREE.MeshStandardMaterial({
      color: C.visor, emissive: C.visor, emissiveIntensity: 1.2,
      metalness: 0.8, roughness: 0.1,
    }));
    this.visor.position.set(0, 0.72, 0.12);
    this.group.add(this.visor);

    // Chin guard
    const chinGeo = new THREE.BoxGeometry(0.14, 0.04, 0.08);
    this.chin = new THREE.Mesh(chinGeo, armorMat.clone());
    this.chin.position.set(0, 0.64, 0.08);
    this.group.add(this.chin);

    // ─── Weapon ──────────────────────────────────────────────
    this._buildWeapon(C, trimMat, accentMat);

    // ─── Back pack / power unit ──────────────────────────────
    const packGeo = new THREE.BoxGeometry(0.16, 0.18, 0.10);
    this.backpack = new THREE.Mesh(packGeo, darkMat.clone());
    this.backpack.position.set(0, 0.50, -0.15);
    this.group.add(this.backpack);

    // Exhaust vents on backpack
    const ventGeo = new THREE.CylinderGeometry(0.02, 0.02, 0.06, 6);
    for (const dx of [-0.05, 0.05]) {
      const vent = new THREE.Mesh(ventGeo, trimMat.clone());
      vent.position.set(dx, 0.56, -0.20);
      vent.rotation.x = Math.PI / 2;
      this.group.add(vent);
    }

    // ─── Base glow rings (double) ────────────────────────────
    const ringGeo1 = new THREE.TorusGeometry(0.24, 0.015, 8, 32);
    this.baseRing1 = new THREE.Mesh(ringGeo1, new THREE.MeshStandardMaterial({
      color: C.primary, emissive: C.primary, emissiveIntensity: 0.9,
      transparent: true, opacity: 0.7,
    }));
    this.baseRing1.rotation.x = -Math.PI / 2;
    this.baseRing1.position.y = 0.02;
    this.group.add(this.baseRing1);

    const ringGeo2 = new THREE.TorusGeometry(0.20, 0.01, 8, 32);
    this.baseRing2 = new THREE.Mesh(ringGeo2, new THREE.MeshStandardMaterial({
      color: C.accent, emissive: C.accent, emissiveIntensity: 0.6,
      transparent: true, opacity: 0.5,
    }));
    this.baseRing2.rotation.x = -Math.PI / 2;
    this.baseRing2.position.y = 0.03;
    this.group.add(this.baseRing2);

    // ─── Shield sphere (initially hidden) ────────────────────
    this.shield = new THREE.Mesh(
      new THREE.SphereGeometry(0.50, 16, 12),
      new THREE.MeshStandardMaterial({
        color: C.primary, emissive: C.primary, emissiveIntensity: 0.4,
        transparent: true, opacity: 0.2, side: THREE.DoubleSide,
      }),
    );
    this.shield.position.y = 0.45;
    this.shield.visible = false;
    this.group.add(this.shield);

    // Shield hex-pattern wireframe ring
    this.shieldRing = new THREE.Mesh(
      new THREE.TorusGeometry(0.48, 0.01, 6, 24),
      new THREE.MeshBasicMaterial({
        color: C.primary, transparent: true, opacity: 0.3,
      }),
    );
    this.shieldRing.position.y = 0.45;
    this.shieldRing.rotation.x = Math.PI / 2;
    this.shieldRing.visible = false;
    this.group.add(this.shieldRing);

    // ─── HP and Energy bars ──────────────────────────────────
    this._hpBarBg = this._makeBar(0.4, 0x222222, 0.95);
    this._hpBarFill = this._makeBar(0.4, 0x00ff44, 0.95);
    this.group.add(this._hpBarBg);
    this.group.add(this._hpBarFill);

    this._enBarBg = this._makeBar(0.32, 0x222222, 0.88);
    this._enBarFill = this._makeBar(0.32, 0xffaa00, 0.88);
    this.group.add(this._enBarBg);
    this.group.add(this._enBarFill);
  }

  /**
   * Build weapon — Agent 1 gets an energy rifle, Agent 2 gets an energy cannon.
   */
  _buildWeapon(C, trimMat, accentMat) {
    const weaponGroup = new THREE.Group();

    if (this.agentId === 1) {
      // ── Energy Rifle ──
      // Barrel
      const barrelGeo = new THREE.CylinderGeometry(0.018, 0.022, 0.35, 6);
      const barrel = new THREE.Mesh(barrelGeo, new THREE.MeshStandardMaterial({
        color: 0x2a2a2a, metalness: 0.9, roughness: 0.2,
      }));
      barrel.rotation.x = Math.PI / 2;
      barrel.position.set(0, 0, 0.18);
      weaponGroup.add(barrel);

      // Stock
      const stockGeo = new THREE.BoxGeometry(0.04, 0.05, 0.12);
      const stock = new THREE.Mesh(stockGeo, new THREE.MeshStandardMaterial({
        color: C.armor, metalness: 0.6, roughness: 0.3,
      }));
      stock.position.set(0, -0.01, -0.04);
      weaponGroup.add(stock);

      // Muzzle glow
      const muzzleGeo = new THREE.SphereGeometry(0.025, 6, 4);
      this.muzzleGlow = new THREE.Mesh(muzzleGeo, accentMat.clone());
      this.muzzleGlow.position.set(0, 0, 0.36);
      weaponGroup.add(this.muzzleGlow);

      // Scope
      const scopeGeo = new THREE.CylinderGeometry(0.012, 0.012, 0.08, 6);
      const scope = new THREE.Mesh(scopeGeo, trimMat.clone());
      scope.position.set(0, 0.035, 0.12);
      scope.rotation.x = Math.PI / 2;
      weaponGroup.add(scope);

      weaponGroup.position.set(0.28, 0.42, 0.05);
    } else {
      // ── Energy Cannon ──
      // Main body
      const bodyGeo = new THREE.CylinderGeometry(0.035, 0.04, 0.28, 8);
      const body = new THREE.Mesh(bodyGeo, new THREE.MeshStandardMaterial({
        color: 0x2a2a2a, metalness: 0.9, roughness: 0.2,
      }));
      body.rotation.x = Math.PI / 2;
      body.position.set(0, 0, 0.14);
      weaponGroup.add(body);

      // Wide muzzle
      const muzzleGeo = new THREE.CylinderGeometry(0.05, 0.035, 0.06, 8);
      const muzzle = new THREE.Mesh(muzzleGeo, trimMat.clone());
      muzzle.rotation.x = Math.PI / 2;
      muzzle.position.set(0, 0, 0.30);
      weaponGroup.add(muzzle);

      // Muzzle glow
      const glowGeo = new THREE.SphereGeometry(0.035, 6, 4);
      this.muzzleGlow = new THREE.Mesh(glowGeo, accentMat.clone());
      this.muzzleGlow.position.set(0, 0, 0.34);
      weaponGroup.add(this.muzzleGlow);

      // Grip
      const gripGeo = new THREE.BoxGeometry(0.04, 0.08, 0.05);
      const grip = new THREE.Mesh(gripGeo, new THREE.MeshStandardMaterial({
        color: C.armor, metalness: 0.6, roughness: 0.3,
      }));
      grip.position.set(0, -0.04, 0.02);
      weaponGroup.add(grip);

      weaponGroup.position.set(-0.28, 0.42, 0.05);
    }

    this.weapon = weaponGroup;
    this.group.add(weaponGroup);
  }

  _makeBar(width, color, y) {
    const geo = new THREE.BoxGeometry(width, 0.035, 0.035);
    const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.85 });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.y = y;
    return mesh;
  }

  // ─── Public API ────────────────────────────────────────────────────

  setPosition(worldPos) {
    this._targetPos.copy(worldPos);
    this._currentPos.copy(worldPos);
    this.group.position.copy(worldPos);
  }

  moveTo(worldPos) {
    this._targetPos.copy(worldPos);
  }

  lookAt(worldPos) {
    const dir = new THREE.Vector3().subVectors(worldPos, this.group.position);
    dir.y = 0;
    if (dir.lengthSq() > 0.001) {
      this.group.lookAt(this.group.position.clone().add(dir));
    }
  }

  setHP(fraction) {
    this._hpBarFill.scale.x = Math.max(0.01, fraction);
    this._hpBarFill.position.x = -(0.2 * (1 - fraction));
    const r = fraction < 0.5 ? 1 : 1 - (fraction - 0.5) * 2;
    const g = fraction > 0.5 ? 1 : fraction * 2;
    this._hpBarFill.material.color.setRGB(r, g, 0);
    this._lowHpFlicker = fraction < 0.3;
  }

  setEnergy(fraction) {
    this._enBarFill.scale.x = Math.max(0.01, fraction);
    this._enBarFill.position.x = -(0.16 * (1 - fraction));
  }

  setShield(active) {
    this._shieldVisible = active;
    this.shield.visible = active;
    this.shieldRing.visible = active;
  }

  applyHitReaction(direction) {
    this._hitDir.copy(direction).normalize().multiplyScalar(0.15);
    this._hitReactionTimer = 0.25;
  }

  hide() { this.group.visible = false; }
  show() { this.group.visible = true; }

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

    // Idle bob — body sways gently
    const bob = Math.sin(this._idleTime * 2.5) * 0.015;
    const tilt = Math.sin(this._idleTime * 1.8) * 0.01;
    this.torso.position.y = 0.48 + bob;
    this.chestPlate.position.y = 0.50 + bob;
    this.core.position.y = 0.50 + bob;
    this.head.position.y = 0.72 + bob;
    this.visor.position.y = 0.72 + bob;
    this.crest.position.y = 0.80 + bob;
    this.chin.position.y = 0.64 + bob;
    this.shoulderL.position.y = 0.58 + bob;
    this.shoulderR.position.y = 0.58 + bob;
    this.upperArmL.position.y = 0.46 + bob;
    this.upperArmR.position.y = 0.46 + bob;
    this.forearmL.position.y = 0.35 + bob;
    this.forearmR.position.y = 0.35 + bob;
    this.backpack.position.y = 0.50 + bob;

    // Subtle leg sway during idle
    const legSway = Math.sin(this._idleTime * 3.0) * 0.02;
    this.thighL.position.x = -0.08 + legSway;
    this.thighR.position.x = 0.08 - legSway;

    // Low-HP flicker — visor and core pulse urgently
    if (this._lowHpFlicker) {
      const flicker = Math.sin(time * 15) > 0.3 ? 1.2 : 0.2;
      this.visor.material.emissiveIntensity = flicker;
      this.core.material.emissiveIntensity = flicker * 0.5;
    } else {
      this.visor.material.emissiveIntensity = 1.2;
      this.core.material.emissiveIntensity = 0.6;
    }

    // Shield pulse (breathe)
    if (this._shieldVisible) {
      this.shield.material.opacity = 0.12 + 0.08 * Math.sin(time * 4);
      this.shieldRing.material.opacity = 0.2 + 0.15 * Math.sin(time * 3 + 1);
      this.shieldRing.rotation.z = time * 0.5;
    }

    // Base ring pulse (double ring counter-rotate)
    this.baseRing1.material.emissiveIntensity = 0.5 + 0.4 * Math.sin(time * 2);
    this.baseRing1.rotation.z = time * 0.3;
    this.baseRing2.material.emissiveIntensity = 0.3 + 0.3 * Math.sin(time * 2.5 + 1);
    this.baseRing2.rotation.z = -time * 0.4;

    // Weapon muzzle glow pulse
    if (this.muzzleGlow) {
      this.muzzleGlow.material.emissiveIntensity = 0.4 + 0.3 * Math.sin(time * 3);
    }
  }
}
