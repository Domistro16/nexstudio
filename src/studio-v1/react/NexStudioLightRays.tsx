"use client";

import { useEffect, useRef, useState } from "react";
import { Mesh, Program, Renderer, Triangle } from "ogl";

type RaysOrigin = "top-left" | "top-center" | "top-right" | "left" | "right" | "bottom-left" | "bottom-center" | "bottom-right";

type LightRaysProps = {
  raysOrigin?: RaysOrigin;
  raysColor?: string;
  secondaryColor?: string;
  raysSpeed?: number;
  lightSpread?: number;
  rayLength?: number;
  fadeDistance?: number;
  saturation?: number;
  followPointer?: boolean;
  pointerInfluence?: number;
  noiseAmount?: number;
  distortion?: number;
  intensity?: number;
  className?: string;
};

const hexToRgb = (hex: string) => {
  const value = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return value ? [parseInt(value[1], 16) / 255, parseInt(value[2], 16) / 255, parseInt(value[3], 16) / 255] : [1, 1, 1];
};

function getAnchorAndDirection(origin: RaysOrigin, width: number, height: number) {
  const outside = 0.22;
  switch (origin) {
    case "top-left": return { anchor: [-0.04 * width, -outside * height], direction: [0.16, 1] };
    case "top-right": return { anchor: [1.04 * width, -outside * height], direction: [-0.16, 1] };
    case "left": return { anchor: [-outside * width, 0.45 * height], direction: [1, 0.08] };
    case "right": return { anchor: [(1 + outside) * width, 0.45 * height], direction: [-1, 0.08] };
    case "bottom-left": return { anchor: [-0.04 * width, (1 + outside) * height], direction: [0.15, -1] };
    case "bottom-center": return { anchor: [0.52 * width, (1 + outside) * height], direction: [0, -1] };
    case "bottom-right": return { anchor: [1.04 * width, (1 + outside) * height], direction: [-0.15, -1] };
    case "top-center":
    default: return { anchor: [0.42 * width, -outside * height], direction: [0.06, 1] };
  }
}

export function NexStudioLightRays({
  raysOrigin = "top-left",
  raysColor = "#8176ff",
  secondaryColor = "#f2a6c8",
  raysSpeed = 0.14,
  lightSpread = 1.28,
  rayLength = 1.8,
  fadeDistance = 1.18,
  saturation = 0.86,
  followPointer = true,
  pointerInfluence = 0.035,
  noiseAmount = 0.025,
  distortion = 0.035,
  intensity = 0.72,
  className = "",
}: LightRaysProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const rendererRef = useRef<Renderer | null>(null);
  const meshRef = useRef<Mesh | null>(null);
  const uniformsRef = useRef<Record<string, { value: unknown }> | null>(null);
  const pointerRef = useRef({ x: 0.5, y: 0.5 });
  const smoothPointerRef = useRef({ x: 0.5, y: 0.5 });
  const frameRef = useRef<number | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.05 });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible || !containerRef.current) return;
    cleanupRef.current?.();

    const node = containerRef.current;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const compact = window.matchMedia("(max-width: 760px)").matches;
    const renderer = new Renderer({ dpr: Math.min(window.devicePixelRatio || 1, compact ? 1.25 : 1.8), alpha: true, antialias: false });
    rendererRef.current = renderer;
    const gl = renderer.gl;
    gl.canvas.style.width = "100%";
    gl.canvas.style.height = "100%";
    gl.canvas.style.display = "block";
    node.replaceChildren(gl.canvas);

    const vertex = `
      attribute vec2 position;
      varying vec2 vUv;
      void main(){
        vUv = position * 0.5 + 0.5;
        gl_Position = vec4(position, 0.0, 1.0);
      }
    `;

    const fragment = `
      precision highp float;
      uniform float iTime;
      uniform vec2 iResolution;
      uniform vec2 rayPos;
      uniform vec2 rayDir;
      uniform vec3 raysColor;
      uniform vec3 secondaryColor;
      uniform float raysSpeed;
      uniform float lightSpread;
      uniform float rayLength;
      uniform float fadeDistance;
      uniform float saturation;
      uniform vec2 pointerPos;
      uniform float pointerInfluence;
      uniform float noiseAmount;
      uniform float distortion;
      uniform float intensity;
      varying vec2 vUv;

      float hash(vec2 p){
        return fract(sin(dot(p, vec2(12.9898,78.233))) * 43758.5453123);
      }

      float rayStrength(vec2 source, vec2 referenceDirection, vec2 coordinate, float seedA, float seedB, float speed){
        vec2 sourceToCoord = coordinate - source;
        vec2 dirNorm = normalize(sourceToCoord);
        float cosAngle = dot(dirNorm, referenceDirection);
        float distortedAngle = cosAngle + distortion * sin(iTime * 0.55 + length(sourceToCoord) * 0.006) * 0.13;
        float spread = pow(max(distortedAngle, 0.0), 1.0 / max(lightSpread, 0.001));
        float distanceToSource = length(sourceToCoord);
        float maxDistance = iResolution.x * rayLength;
        float lengthFalloff = clamp((maxDistance - distanceToSource) / maxDistance, 0.0, 1.0);
        float fade = clamp((iResolution.x * fadeDistance - distanceToSource) / (iResolution.x * fadeDistance), 0.28, 1.0);
        float base = clamp(
          (0.42 + 0.14 * sin(distortedAngle * seedA + iTime * speed)) +
          (0.26 + 0.18 * cos(-distortedAngle * seedB + iTime * speed * 0.84)),
          0.0, 1.0
        );
        return base * lengthFalloff * fade * spread;
      }

      void main(){
        vec2 coordinate = vec2(gl_FragCoord.x, iResolution.y - gl_FragCoord.y);
        vec2 finalDirection = rayDir;
        if(pointerInfluence > 0.0){
          vec2 pointerScreen = pointerPos * iResolution.xy;
          vec2 pointerDirection = normalize(pointerScreen - rayPos);
          finalDirection = normalize(mix(rayDir, pointerDirection, pointerInfluence));
        }

        float rayA = rayStrength(rayPos, finalDirection, coordinate, 34.1, 19.7, 1.15 * raysSpeed);
        float rayB = rayStrength(rayPos, finalDirection, coordinate, 21.4, 17.1, 0.78 * raysSpeed);
        float rayC = rayStrength(rayPos + vec2(iResolution.x * 0.12, 0.0), finalDirection, coordinate, 13.8, 29.3, 0.52 * raysSpeed) * 0.52;
        float strength = (rayA * 0.52 + rayB * 0.34 + rayC * 0.28) * intensity;

        float colourDrift = 0.5 + 0.5 * sin(iTime * 0.075 + vUv.x * 2.6 + vUv.y * 0.7);
        vec3 colour = mix(raysColor, secondaryColor, smoothstep(0.18, 0.84, colourDrift));
        float neutralMix = dot(colour, vec3(0.299,0.587,0.114));
        colour = mix(vec3(neutralMix), colour, saturation);

        float edge = smoothstep(0.02, 0.22, vUv.y) * smoothstep(0.01, 0.16, 1.0 - vUv.x);
        float grain = (hash(coordinate * 0.055 + iTime * 0.01) - 0.5) * noiseAmount;
        vec3 rgb = max(vec3(0.0), colour * strength * edge + grain);
        gl_FragColor = vec4(rgb, clamp(strength * 0.88, 0.0, 0.82));
      }
    `;

    const uniforms = {
      iTime: { value: 0 },
      iResolution: { value: [1, 1] },
      rayPos: { value: [0, 0] },
      rayDir: { value: [0, 1] },
      raysColor: { value: hexToRgb(raysColor) },
      secondaryColor: { value: hexToRgb(secondaryColor) },
      raysSpeed: { value: raysSpeed },
      lightSpread: { value: lightSpread },
      rayLength: { value: rayLength },
      fadeDistance: { value: fadeDistance },
      saturation: { value: saturation },
      pointerPos: { value: [0.5, 0.5] },
      pointerInfluence: { value: compact || reducedMotion ? 0 : pointerInfluence },
      noiseAmount: { value: noiseAmount },
      distortion: { value: reducedMotion ? 0 : distortion },
      intensity: { value: intensity },
    };
    uniformsRef.current = uniforms;

    const geometry = new Triangle(gl);
    const program = new Program(gl, { vertex, fragment, uniforms });
    const mesh = new Mesh(gl, { geometry, program });
    meshRef.current = mesh;

    const resize = () => {
      const widthCss = Math.max(1, node.clientWidth);
      const heightCss = Math.max(1, node.clientHeight);
      renderer.setSize(widthCss, heightCss);
      const width = widthCss * renderer.dpr;
      const height = heightCss * renderer.dpr;
      uniforms.iResolution.value = [width, height];
      const { anchor, direction } = getAnchorAndDirection(raysOrigin, width, height);
      uniforms.rayPos.value = anchor;
      uniforms.rayDir.value = direction;
    };

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(node);
    resize();

    const onPointerMove = (event: PointerEvent) => {
      if (compact || reducedMotion) return;
      const rect = node.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      pointerRef.current = {
        x: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
        y: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
      };
    };
    if (followPointer && !compact && !reducedMotion) node.addEventListener("pointermove", onPointerMove, { passive: true });

    let previous = 0;
    const render = (time: number) => {
      if (!rendererRef.current || !meshRef.current) return;
      if (!compact || time - previous >= 32) {
        previous = time;
        const smoothing = 0.965;
        smoothPointerRef.current.x = smoothPointerRef.current.x * smoothing + pointerRef.current.x * (1 - smoothing);
        smoothPointerRef.current.y = smoothPointerRef.current.y * smoothing + pointerRef.current.y * (1 - smoothing);
        uniforms.pointerPos.value = [smoothPointerRef.current.x, smoothPointerRef.current.y];
        uniforms.iTime.value = reducedMotion ? 0 : time * 0.001;
        renderer.render({ scene: mesh });
      }
      if (!reducedMotion) frameRef.current = requestAnimationFrame(render);
    };

    if (reducedMotion) render(0);
    else frameRef.current = requestAnimationFrame(render);

    cleanupRef.current = () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
      resizeObserver.disconnect();
      node.removeEventListener("pointermove", onPointerMove);
      const canvas = gl.canvas;
      const loseContext = gl.getExtension("WEBGL_lose_context");
      loseContext?.loseContext();
      if (canvas.parentNode === node) node.removeChild(canvas);
      rendererRef.current = null;
      meshRef.current = null;
      uniformsRef.current = null;
    };

    return () => cleanupRef.current?.();
  }, [visible, raysOrigin, raysColor, secondaryColor, raysSpeed, lightSpread, rayLength, fadeDistance, saturation, followPointer, pointerInfluence, noiseAmount, distortion, intensity]);

  return <div ref={containerRef} className={`nxs-light-rays ${className}`.trim()} aria-hidden="true" />;
}
