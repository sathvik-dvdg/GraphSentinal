// [Windows] GraphSentinel
import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

function ShieldShape() {
  const meshRef = useRef();

  const geometry = useMemo(() => {
    const shieldShape = new THREE.Shape();
    shieldShape.moveTo(0, 1);
    shieldShape.quadraticCurveTo(1, 1, 1, 0);
    shieldShape.quadraticCurveTo(1, -0.8, 0, -1.5);
    shieldShape.quadraticCurveTo(-1, -0.8, -1, 0);
    shieldShape.quadraticCurveTo(-1, 1, 0, 1);

    const extrudeSettings = { depth: 0.2, bevelEnabled: true, bevelThickness: 0.1, bevelSize: 0.1, bevelSegments: 5 };
    return new THREE.ExtrudeGeometry(shieldShape, extrudeSettings);
  }, []);

  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.01;
    }
  });

  return (
    <mesh ref={meshRef} geometry={geometry} rotation={[Math.PI, 0, 0]}>
      <meshPhongMaterial 
        color={0x80f9ff} 
        emissive={0x004444} 
        specular={0xffffff} 
        shininess={100} 
        transparent={true} 
        opacity={0.95} 
      />
    </mesh>
  );
}

function RotatingRing({ radius, index }) {
  const meshRef = useRef();
  
  const speed = useMemo(() => ({
    x: (Math.random() - 0.5) * 0.015,
    y: (Math.random() - 0.5) * 0.015,
    z: (Math.random() - 0.5) * 0.01
  }), []);

  const initialRotation = useMemo(() => [Math.random() * Math.PI, Math.random() * Math.PI, 0], []);

  useFrame(() => {
    if (meshRef.current) {
      meshRef.current.rotation.x += speed.x;
      meshRef.current.rotation.y += speed.y;
      meshRef.current.rotation.z += speed.z;
    }
  });

  return (
    <mesh ref={meshRef} rotation={initialRotation}>
      <torusGeometry args={[radius, 0.03, 16, 100]} />
      <meshBasicMaterial 
        color={0x80f9ff} 
        wireframe={true} 
        transparent={true} 
        opacity={0.4 - (index * 0.1)} 
      />
    </mesh>
  );
}

function Scene() {
  const groupRef = useRef();

  useFrame(({ mouse, clock }) => {
    if (groupRef.current) {
      // Mouse tracking
      const targetRotationY = mouse.x * 0.4;
      const targetRotationX = -mouse.y * 0.4;
      
      groupRef.current.rotation.y += (targetRotationY - groupRef.current.rotation.y) * 0.05 + 0.005;
      groupRef.current.rotation.x += (targetRotationX - groupRef.current.rotation.x) * 0.05;
      
      // Subtle float
      groupRef.current.position.y = Math.sin(clock.getElapsedTime()) * 0.15;
    }
  });

  return (
    <group ref={groupRef}>
      <ShieldShape />
      {[0, 1, 2].map((i) => (
        <RotatingRing key={i} index={i} radius={1.8 + (i * 0.4)} />
      ))}
    </group>
  );
}

export default function Shield3D() {
  return (
    <div className="w-full h-full absolute inset-0 z-10 pointer-events-auto">
      <Canvas camera={{ position: [0, 0, 6], fov: 75 }}>
        <ambientLight intensity={0.4} />
        <pointLight position={[5, 5, 5]} intensity={2.5} color={0x80f9ff} />
        <Scene />
      </Canvas>
    </div>
  );
}
