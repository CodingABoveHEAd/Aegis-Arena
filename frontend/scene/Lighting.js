/**
 * Lighting.js — Dramatic arena lighting with dynamic agent point-lights.
 */

import * as THREE from 'three';

export class Lighting {
  /**
   * @param {THREE.Scene} scene
   */
  constructor(scene) {
    this.scene = scene;

    // Ambient base
    this.ambient = new THREE.AmbientLight(0x223344, 0.3);
    scene.add(this.ambient);

    // Hemisphere sky/ground
    this.hemi = new THREE.HemisphereLight(0x223355, 0x0a0a1a, 0.25);
    scene.add(this.hemi);

    // Main directional (sun-like)
    this.dir = new THREE.DirectionalLight(0xaabbdd, 0.8);
    this.dir.position.set(6, 12, 8);
    this.dir.castShadow = true;
    this.dir.shadow.mapSize.set(2048, 2048);
    this.dir.shadow.camera.left   = -6;
    this.dir.shadow.camera.right  =  10;
    this.dir.shadow.camera.top    =  10;
    this.dir.shadow.camera.bottom = -6;
    this.dir.shadow.camera.near   =  1;
    this.dir.shadow.camera.far    =  30;
    this.dir.shadow.bias = -0.002;
    scene.add(this.dir);

    // Overhead spot for arena centre
    this.spot = new THREE.SpotLight(0x6688cc, 0.4, 20, Math.PI / 5, 0.5, 1);
    this.spot.position.set(3.5, 10, 3.5);
    this.spot.target.position.set(3.5, 0, 3.5);
    scene.add(this.spot);
    scene.add(this.spot.target);

    // Agent-following point lights
    this.pointA1 = new THREE.PointLight(0x00d4ff, 0.6, 6, 2);
    this.pointA1.position.set(0, 2, 0);
    scene.add(this.pointA1);

    this.pointA2 = new THREE.PointLight(0xff3333, 0.6, 6, 2);
    this.pointA2.position.set(7, 2, 7);
    scene.add(this.pointA2);
  }

  /**
   * Move agent point-lights to follow agent world positions.
   * @param {THREE.Vector3} posA1
   * @param {THREE.Vector3} posA2
   */
  updateAgentPositions(posA1, posA2) {
    if (posA1) {
      this.pointA1.position.set(posA1.x, posA1.y + 2, posA1.z);
    }
    if (posA2) {
      this.pointA2.position.set(posA2.x, posA2.y + 2, posA2.z);
    }
  }
}
