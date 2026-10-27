import { useEffect, useRef } from "react";
import * as THREE from "three";

interface Props {
  torsoPitch: number;      // deg
  torsoRoll: number;       // deg
  neckRelativePitch: number; // deg (absolute)
  condition: string;
  color: string;
}

const DEG = Math.PI / 180;

/**
 * A minimal 3-D posture avatar (torso + head) that tilts to match the live
 * sensor angles. Vanilla three.js in a ref-managed canvas -- no react-three
 * dependency to keep the bundle lean.
 */
export default function PostureAvatar({
  torsoPitch,
  torsoRoll,
  neckRelativePitch,
  condition,
  color,
}: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const torsoRef = useRef<THREE.Mesh>();
  const headRef = useRef<THREE.Mesh>();
  const torsoMatRef = useRef<THREE.MeshStandardMaterial>();
  const frameRef = useRef<number>();

  // Latest targets (mutated each render; the animation loop eases toward them).
  const target = useRef({ pitch: 0, roll: 0, neck: 0, color: new THREE.Color(color) });

  useEffect(() => {
    const mount = mountRef.current!;
    const width = mount.clientWidth;
    const height = mount.clientHeight;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#0b1220");

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
    camera.position.set(0, 1.2, 6);
    camera.lookAt(0, 1, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dir = new THREE.DirectionalLight(0xffffff, 0.8);
    dir.position.set(3, 5, 4);
    scene.add(dir);

    // Hips pivot (root). Torso rotates about the hips.
    const hips = new THREE.Group();
    hips.position.y = 0;
    scene.add(hips);

    const torsoMat = new THREE.MeshStandardMaterial({ color, roughness: 0.5 });
    torsoMatRef.current = torsoMat;
    const torso = new THREE.Mesh(new THREE.BoxGeometry(1.1, 1.8, 0.6), torsoMat);
    torso.position.y = 0.9; // sits on top of hips pivot
    hips.add(torso);
    torsoRef.current = torso;

    // Neck pivot at top of torso; head is a child so it inherits torso tilt.
    const neckPivot = new THREE.Group();
    neckPivot.position.y = 1.0; // top of torso (local to torso)
    torso.add(neckPivot);

    const headMat = new THREE.MeshStandardMaterial({ color: "#cbd5e1", roughness: 0.4 });
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.42, 24, 24), headMat);
    head.position.y = 0.5;
    neckPivot.add(head);
    headRef.current = head;

    // Ground reference grid.
    const grid = new THREE.GridHelper(8, 8, 0x1e293b, 0x1e293b);
    grid.position.y = -0.05;
    scene.add(grid);

    const animate = () => {
      frameRef.current = requestAnimationFrame(animate);
      const t = target.current;
      // Ease current rotations toward targets.
      hips.rotation.x += (t.pitch * DEG - hips.rotation.x) * 0.15;
      hips.rotation.z += (-t.roll * DEG - hips.rotation.z) * 0.15;
      neckPivot.rotation.x += (t.neck * DEG - neckPivot.rotation.x) * 0.15;
      torsoMat.color.lerp(t.color, 0.1);
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Push new targets whenever props change.
  useEffect(() => {
    target.current.pitch = torsoPitch;
    target.current.roll = torsoRoll;
    target.current.neck = neckRelativePitch;
    target.current.color = new THREE.Color(color);
  }, [torsoPitch, torsoRoll, neckRelativePitch, color]);

  return (
    <div className="avatar-wrap">
      <div ref={mountRef} className="avatar-canvas" />
      <div className="avatar-caption" style={{ color }}>
        {condition ? condition.replace(/_/g, " ") : "waiting..."}
      </div>
    </div>
  );
}
