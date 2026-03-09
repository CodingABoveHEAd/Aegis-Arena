/**
 * CameraRig.js — Overview / Action-cam modes, proximity zoom, camera shake.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const OVERVIEW = {
  pos: new THREE.Vector3(3.5, 11, 14),
  target: new THREE.Vector3(3.5, 0, 3.5),
};

export class CameraRig {
  /**
   * @param {THREE.PerspectiveCamera} camera
   * @param {HTMLElement} domElement — renderer canvas.
   */
  constructor(camera, domElement) {
    this.camera = camera;
    this.controls = new OrbitControls(camera, domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.minPolarAngle = 0.3;
    this.controls.maxPolarAngle = Math.PI / 2.1;
    this.controls.minDistance = 4;
    this.controls.maxDistance = 20;

    this.mode = 'overview'; // 'overview' | 'action'

    // Shake state
    this._shakeIntensity = 0;
    this._shakeDuration = 0;
    this._shakeTimer = 0;

    // Action-cam state
    this._actionTarget = null;
    this._actionTimer = 0;

    // Init
    camera.position.copy(OVERVIEW.pos);
    this.controls.target.copy(OVERVIEW.target);
    this.controls.update();
  }

  // ─── API ───────────────────────────────────────────────────────────

  /** Smoothly return to overview. */
  setOverview() {
    this.mode = 'overview';
    this._actionTarget = null;
  }

  /**
   * Briefly switch to action cam focusing on a world point.
   * @param {THREE.Vector3} focusPoint
   * @param {number} duration — seconds.
   */
  triggerActionCam(focusPoint, duration = 1.2) {
    this.mode = 'action';
    this._actionTarget = focusPoint.clone();
    this._actionTimer = duration;
  }

  /**
   * Trigger camera shake.
   * @param {number} intensity — shake magnitude in world units.
   * @param {number} duration — seconds.
   */
  shake(intensity = 0.08, duration = 0.3) {
    this._shakeIntensity = intensity;
    this._shakeDuration = duration;
    this._shakeTimer = duration;
  }

  // ─── Proximity zoom ───────────────────────────────────────────────

  /**
   * Zoom closer when agents are near each other.
   * @param {THREE.Vector3} a1
   * @param {THREE.Vector3} a2
   */
  updateProximityZoom(a1, a2) {
    if (!a1 || !a2 || this.mode !== 'overview') return;
    const dist = a1.distanceTo(a2);
    // When distance < 3, zoom to minDistance; when > 6, zoom to default
    const t = THREE.MathUtils.clamp((dist - 2) / 5, 0, 1);
    const desiredDist = THREE.MathUtils.lerp(6, 12, t);
    const currentDist = this.camera.position.distanceTo(this.controls.target);
    const newDist = THREE.MathUtils.lerp(currentDist, desiredDist, 0.02);
    const direction = this.camera.position.clone().sub(this.controls.target).normalize();
    this.camera.position.copy(this.controls.target.clone().add(direction.multiplyScalar(newDist)));
  }

  // ─── Update ────────────────────────────────────────────────────────

  update(dt) {
    // Action cam
    if (this.mode === 'action' && this._actionTarget) {
      this._actionTimer -= dt;
      const offset = new THREE.Vector3(2, 4, 3);
      const desiredPos = this._actionTarget.clone().add(offset);
      this.camera.position.lerp(desiredPos, 3 * dt);
      this.controls.target.lerp(this._actionTarget, 3 * dt);

      if (this._actionTimer <= 0) {
        this.setOverview();
      }
    }

    // Overview lerp
    if (this.mode === 'overview') {
      this.camera.position.lerp(OVERVIEW.pos, 1.5 * dt);
      this.controls.target.lerp(OVERVIEW.target, 1.5 * dt);
    }

    // Camera shake
    if (this._shakeTimer > 0) {
      this._shakeTimer -= dt;
      const t = this._shakeTimer / this._shakeDuration;
      const mag = this._shakeIntensity * t;
      this.camera.position.x += (Math.random() - 0.5) * 2 * mag;
      this.camera.position.y += (Math.random() - 0.5) * 2 * mag;
      this.camera.position.z += (Math.random() - 0.5) * 2 * mag;
    }

    this.controls.update();
  }
}
