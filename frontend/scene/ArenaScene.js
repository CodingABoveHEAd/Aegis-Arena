/**
 * ArenaScene.js — 8×8 tactical arena with tile meshes, walls, pillars, etc.
 *
 * Grid mapping: backend (row, col) → Three.js (x=col, y=0, z=row).
 */

import * as THREE from 'three';

// ── Tile colours ──
const TILE_MAT = {
  EMPTY: { color: 0x0a1520, roughness: 0.8, metalness: 0.4 },
  COVER: { color: 0x0a2a12, roughness: 0.6, metalness: 0.4, emissive: 0x003300, emissiveIntensity: 0.15 },
  ENERGY: { color: 0x1a1200, roughness: 0.7, metalness: 0.3, emissive: 0xaa5500, emissiveIntensity: 0.3 },
  TRAP: { color: 0x200000, roughness: 0.7, metalness: 0.3, emissive: 0x660000, emissiveIntensity: 0.25 },
  ELEVATED: { color: 0x0a1520, roughness: 0.7, metalness: 0.5, emissive: 0x112244, emissiveIntensity: 0.1 },
};

export class ArenaScene {
  /**
   * @param {THREE.Scene} scene — the root scene to add meshes to.
   */
  constructor(scene) {
    this.scene = scene;
    /** @type {THREE.Mesh[][]} row-major tile mesh array */
    this.tileMeshes = [];
    /** @type {THREE.Group[][]} per-tile decoration group (crystals, spikes, walls) */
    this.tileDecorations = [];
    /** @type {number[]} random phase offsets for pulsing tiles */
    this.tilePhases = [];
    /** @type {THREE.Mesh[]} energy crystal meshes (for spin animation) */
    this.energyCrystals = [];
    /** @type {THREE.Group} root group for entire arena */
    this.group = new THREE.Group();
    scene.add(this.group);
  }

  // ───────────────────────────────────────────────────────────────────────
  // Build
  // ───────────────────────────────────────────────────────────────────────

  /**
   * Build the full arena from the grid provided by the backend.
   * @param {string[][]} grid — 8×8 array of tile-type strings.
   * @param {number[][]} elevatedTiles — list of [row,col] elevated positions.
   */
  build(grid, elevatedTiles = []) {
    const elevSet = new Set(elevatedTiles.map(([r, c]) => `${r},${c}`));
    const tileGeo = new THREE.BoxGeometry(0.92, 0.15, 0.92);

    for (let row = 0; row < 8; row++) {
      this.tileMeshes[row] = [];
      this.tileDecorations[row] = [];
      for (let col = 0; col < 8; col++) {
        const type = grid[row][col];
        const matDef = TILE_MAT[type] || TILE_MAT.EMPTY;
        const mat = new THREE.MeshStandardMaterial({ ...matDef });

        const isElevated = elevSet.has(`${row},${col}`) || type === 'ELEVATED';
        const yBase = isElevated ? 0.4 : 0;

        // Tile mesh
        const mesh = new THREE.Mesh(tileGeo, mat);
        mesh.position.set(col, yBase, row);
        mesh.receiveShadow = true;
        mesh.userData = { row, col, type };
        this.group.add(mesh);
        this.tileMeshes[row][col] = mesh;

        // Elevated side face
        if (isElevated) {
          this._addElevatedSide(col, row, yBase);
        }

        // Phase offset for animation
        this.tilePhases.push(Math.random() * Math.PI * 2);

        // Decorations
        const decoGroup = new THREE.Group();
        decoGroup.position.set(col, yBase, row);
        this.group.add(decoGroup);
        this.tileDecorations[row][col] = decoGroup;

        if (type === 'COVER') this._addCoverWall(decoGroup);
        if (type === 'ENERGY') this._addEnergyCrystal(decoGroup);
        if (type === 'TRAP') this._addTrapSpikes(decoGroup);
        if (isElevated && type !== 'COVER' && type !== 'ENERGY' && type !== 'TRAP') {
          this._addElevatedParticle(decoGroup);
        }
      }
    }

    this._addPlatform();
    this._addBorderWalls();
    this._addCornerPillars();
    this._addGridLines();
  }

  // ── Decorations ─────────────────────────────────────────────────────

  _addElevatedSide(x, z, yBase) {
    const sideGeo = new THREE.BoxGeometry(0.92, yBase + 0.15, 0.92);
    const sideMat = new THREE.MeshStandardMaterial({
      color: 0x152535, roughness: 0.6, metalness: 0.5,
    });
    const side = new THREE.Mesh(sideGeo, sideMat);
    side.position.set(x, (yBase + 0.15) / 2 - 0.075, z);
    side.receiveShadow = true;
    this.group.add(side);
  }

  _addCoverWall(parent) {
    const wallGeo = new THREE.BoxGeometry(0.3, 0.6, 0.92);
    const wallMat = new THREE.MeshStandardMaterial({
      color: 0x0a2a12, roughness: 0.5, metalness: 0.5,
      emissive: 0x003300, emissiveIntensity: 0.1,
    });
    const wall = new THREE.Mesh(wallGeo, wallMat);
    wall.position.set(-0.31, 0.37, 0);
    wall.castShadow = true;
    wall.receiveShadow = true;
    parent.add(wall);
  }

  _addEnergyCrystal(parent) {
    const crystalGeo = new THREE.OctahedronGeometry(0.12);
    const crystalMat = new THREE.MeshStandardMaterial({
      color: 0xffaa00, emissive: 0xaa5500, emissiveIntensity: 0.6,
      metalness: 0.6, roughness: 0.2,
    });
    const crystal = new THREE.Mesh(crystalGeo, crystalMat);
    crystal.position.set(0, 0.4, 0);
    parent.add(crystal);
    this.energyCrystals.push(crystal);
  }

  _addTrapSpikes(parent) {
    const spikeGeo = new THREE.ConeGeometry(0.06, 0.2, 6);
    const spikeMat = new THREE.MeshStandardMaterial({
      color: 0x660000, emissive: 0x440000, emissiveIntensity: 0.3,
      metalness: 0.6, roughness: 0.4,
    });
    const offsets = [
      [0.15, 0.15], [-0.15, 0.15], [0.15, -0.15], [-0.15, -0.15],
    ];
    for (const [dx, dz] of offsets) {
      const spike = new THREE.Mesh(spikeGeo, spikeMat);
      spike.position.set(dx, 0.17, dz);
      parent.add(spike);
    }
  }

  _addElevatedParticle(parent) {
    // Subtle upward particle drift — represented as tiny glowing sphere
    const geo = new THREE.SphereGeometry(0.025, 4, 4);
    const mat = new THREE.MeshBasicMaterial({ color: 0x4488cc, transparent: true, opacity: 0.5 });
    for (let i = 0; i < 3; i++) {
      const p = new THREE.Mesh(geo, mat.clone());
      p.position.set((Math.random() - 0.5) * 0.4, 0.2 + Math.random() * 0.3, (Math.random() - 0.5) * 0.4);
      p.userData._driftPhase = Math.random() * Math.PI * 2;
      parent.add(p);
    }
  }

  // ── Arena infrastructure ────────────────────────────────────────────

  _addPlatform() {
    const geo = new THREE.BoxGeometry(8.5, 0.3, 8.5);
    const mat = new THREE.MeshStandardMaterial({
      color: 0x071018, emissive: 0x001122, emissiveIntensity: 0.15,
      roughness: 0.9, metalness: 0.3,
    });
    const platform = new THREE.Mesh(geo, mat);
    platform.position.set(3.5, -0.22, 3.5);
    platform.receiveShadow = true;
    this.group.add(platform);
  }

  _addBorderWalls() {
    const wallMat = new THREE.MeshStandardMaterial({ color: 0x0d2035, metalness: 0.8, roughness: 0.4 });
    const trimMat = new THREE.MeshStandardMaterial({ color: 0x00aaff, emissive: 0x00aaff, emissiveIntensity: 0.8 });

    const specs = [
      { size: [8.2, 0.8, 0.1], pos: [3.5, 0.33, -0.55], trim: [8.2, 0.03, 0.03], trimPos: [3.5, 0.74, -0.55] },
      { size: [8.2, 0.8, 0.1], pos: [3.5, 0.33, 7.55],  trim: [8.2, 0.03, 0.03], trimPos: [3.5, 0.74, 7.55] },
      { size: [0.1, 0.8, 8.2], pos: [-0.55, 0.33, 3.5],  trim: [0.03, 0.03, 8.2], trimPos: [-0.55, 0.74, 3.5] },
      { size: [0.1, 0.8, 8.2], pos: [7.55, 0.33, 3.5],   trim: [0.03, 0.03, 8.2], trimPos: [7.55, 0.74, 3.5] },
    ];

    for (const s of specs) {
      const wall = new THREE.Mesh(new THREE.BoxGeometry(...s.size), wallMat);
      wall.position.set(...s.pos);
      wall.receiveShadow = true;
      this.group.add(wall);

      const trim = new THREE.Mesh(new THREE.BoxGeometry(...s.trim), trimMat);
      trim.position.set(...s.trimPos);
      this.group.add(trim);
    }
  }

  _addCornerPillars() {
    const pillarMat = new THREE.MeshStandardMaterial({ color: 0x152535, metalness: 0.7, roughness: 0.4 });
    const ringMat   = new THREE.MeshStandardMaterial({ color: 0x0066aa, emissive: 0x0066aa, emissiveIntensity: 0.9 });

    const corners = [[-0.5, -0.5], [7.5, -0.5], [-0.5, 7.5], [7.5, 7.5]];
    for (const [x, z] of corners) {
      const pillar = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 3.0, 8), pillarMat);
      pillar.position.set(x, 1.5, z);
      pillar.castShadow = true;
      this.group.add(pillar);

      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.02, 8, 32), ringMat);
      ring.rotation.x = Math.PI / 2;
      ring.position.set(x, 3.05, z);
      this.group.add(ring);
    }
  }

  _addGridLines() {
    const points = [];
    for (let i = 0; i <= 8; i++) {
      const v = i - 0.5;
      points.push(new THREE.Vector3(-0.5, 0.08, v), new THREE.Vector3(7.5, 0.08, v));
      points.push(new THREE.Vector3(v, 0.08, -0.5), new THREE.Vector3(v, 0.08, 7.5));
    }
    const geo = new THREE.BufferGeometry().setFromPoints(points);
    const mat = new THREE.LineBasicMaterial({ color: 0x1a3a5c, transparent: true, opacity: 0.4 });
    const lines = new THREE.LineSegments(geo, mat);
    this.group.add(lines);
  }

  // ───────────────────────────────────────────────────────────────────────
  // Per-frame update
  // ───────────────────────────────────────────────────────────────────────

  update(time) {
    let idx = 0;
    for (let row = 0; row < 8; row++) {
      for (let col = 0; col < 8; col++) {
        const mesh = this.tileMeshes[row]?.[col];
        if (!mesh) { idx++; continue; }
        const type = mesh.userData.type;
        const phase = this.tilePhases[idx] || 0;

        if (type === 'ENERGY') {
          mesh.material.emissiveIntensity = 0.3 + 0.3 * Math.sin(time * 2.0 + phase);
        } else if (type === 'TRAP') {
          mesh.material.emissiveIntensity = 0.2 + 0.2 * Math.sin(time * 3.0 + phase);
        }

        // Drift particles on elevated tiles
        const deco = this.tileDecorations[row]?.[col];
        if (deco) {
          for (const child of deco.children) {
            if (child.userData._driftPhase !== undefined) {
              child.position.y = 0.2 + 0.25 * Math.sin(time * 1.2 + child.userData._driftPhase);
              child.material.opacity = 0.3 + 0.2 * Math.sin(time * 1.5 + child.userData._driftPhase);
            }
          }
        }
        idx++;
      }
    }

    // Spin energy crystals
    for (const crystal of this.energyCrystals) {
      crystal.rotation.y = time * 1.2;
      crystal.rotation.x = Math.sin(time * 0.8) * 0.3;
    }
  }

  // ───────────────────────────────────────────────────────────────────────
  // Tile updates from backend state
  // ───────────────────────────────────────────────────────────────────────

  /**
   * Update tile visuals when the grid changes (e.g. trap triggered).
   * @param {string[][]} grid
   */
  updateGrid(grid) {
    for (let row = 0; row < 8; row++) {
      for (let col = 0; col < 8; col++) {
        const mesh = this.tileMeshes[row]?.[col];
        if (!mesh) continue;
        const newType = grid[row][col];
        if (mesh.userData.type !== newType) {
          const matDef = TILE_MAT[newType] || TILE_MAT.EMPTY;
          mesh.material.color.set(matDef.color);
          mesh.material.emissive.set(matDef.emissive || 0x000000);
          mesh.material.emissiveIntensity = matDef.emissiveIntensity || 0;
          mesh.userData.type = newType;
        }
      }
    }
  }

  /**
   * Convert backend (row, col) to Three.js Vector3 world position.
   * @param {number[]} pos — [row, col]
   * @returns {THREE.Vector3}
   */
  gridToWorld(pos) {
    const [row, col] = pos;
    // Check if this tile is elevated
    const mesh = this.tileMeshes[row]?.[col];
    const yBase = mesh ? mesh.position.y : 0;
    return new THREE.Vector3(col, yBase + 0.08, row);
  }
}
