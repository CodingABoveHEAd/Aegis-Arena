/**
 * main.js — Three.js bootstrap, render loop, and module wiring.
 */

import * as THREE from 'three';
import { CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js';

import { ArenaScene } from './scene/ArenaScene.js';
import { Lighting }    from './scene/Lighting.js';
import { AgentMesh }   from './scene/AgentMesh.js';
import { CameraRig }   from './scene/CameraRig.js';
import { Effects }     from './scene/Effects.js';

import { HUD }          from './ui/HUD.js';
import { ActionPanel }  from './ui/ActionPanel.js';
import { MenuScreen }   from './ui/MenuScreen.js';

import { GameController } from './game/GameController.js';

// ─── Renderer ────────────────────────────────────────────────────────

const container   = document.getElementById('canvas-container');
const css2dContainer = document.getElementById('css2d-container');

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.outputEncoding = THREE.sRGBEncoding;
container.appendChild(renderer.domElement);

const labelRenderer = new CSS2DRenderer();
labelRenderer.setSize(window.innerWidth, window.innerHeight);
labelRenderer.domElement.style.position = 'absolute';
labelRenderer.domElement.style.top = '0';
labelRenderer.domElement.style.pointerEvents = 'none';
css2dContainer.appendChild(labelRenderer.domElement);

// ─── Scene + Camera ──────────────────────────────────────────────────

const scene  = new THREE.Scene();
scene.background = new THREE.Color(0x050810);
scene.fog = new THREE.FogExp2(0x050810, 0.04);

const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 100);

// ─── Subsystems ──────────────────────────────────────────────────────

const arenaScene = new ArenaScene(scene);
const lighting   = new Lighting(scene);
const agent1     = new AgentMesh(scene, 1);
const agent2     = new AgentMesh(scene, 2);
const cameraRig  = new CameraRig(camera, renderer.domElement);
const effects    = new Effects(scene, labelRenderer);

agent1.hide();
agent2.hide();

// ─── UI ──────────────────────────────────────────────────────────────

const hud = new HUD();

let controller;

const actionPanel = new ActionPanel((action) => {
  if (controller) controller.handleHumanAction(action);
});

const menuScreen = new MenuScreen(async (mode, humanSide) => {
  await controller.startGame(mode, humanSide);
});

// ─── Controller ──────────────────────────────────────────────────────

controller = new GameController({
  arena: arenaScene,
  lighting,
  agent1,
  agent2,
  cameraRig,
  effects,
  hud,
  actionPanel,
});

controller.onReturnToMenu(() => {
  menuScreen.show();
});

// ─── Render loop ─────────────────────────────────────────────────────

const clock = new THREE.Clock();

function animate() {
  requestAnimationFrame(animate);

  const dt   = clock.getDelta();
  const time = clock.getElapsedTime();

  // Update subsystems
  arenaScene.update(time);
  agent1.update(dt, time);
  agent2.update(dt, time);
  cameraRig.update(dt);
  effects.update(dt, time);

  // Proximity zoom
  if (agent1.group.visible && agent2.group.visible) {
    cameraRig.updateProximityZoom(agent1.group.position, agent2.group.position);
  }

  // Render
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
}

animate();

// ─── Resize ──────────────────────────────────────────────────────────

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  labelRenderer.setSize(window.innerWidth, window.innerHeight);
});
