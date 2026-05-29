import React, { useRef, useEffect } from 'react';
import { useTheme } from '../context/ThemeContext';

const THEMES = {
  dark: {
    mode: 1.0,
    bg1: [0.008, 0.024, 0.09],
    bg2: [0.059, 0.09, 0.165],
    line1: [0.145, 0.388, 0.922],
    line2: [0.114, 0.306, 0.847],
  },
  light: {
    mode: 0.0,
    bg1: [1.0, 1.0, 1.0],
    bg2: [0.886, 0.91, 0.941],
    line1: [0.145, 0.388, 0.922],
    line2: [0.114, 0.306, 0.847],
  },
} as const;

const VERTEX_SHADER = `
  attribute vec2 a_position;
  void main() {
    gl_Position = vec4(a_position, 0, 1);
  }
`;

const FRAGMENT_SHADER = `
  precision mediump float;
  uniform vec2 iResolution;
  uniform float iTime;
  uniform float uSpeed;
  uniform float uLineCount;
  uniform float uAmplitude;
  uniform float uYOffset;
  uniform float uThemeMode;
  uniform vec3 uBgColor1;
  uniform vec3 uBgColor2;
  uniform vec3 uLineColor1;
  uniform vec3 uLineColor2;

  const float MAX_LINES = 20.0;

  float wave(vec2 uv, float speed, float yPos, float thickness, float softness) {
    float falloff = smoothstep(1., 0.3, abs(uv.x));
    float y = falloff * (sin(iTime * speed + uv.x * 12.0) * 0.7 + cos(iTime * speed * 0.5 + uv.x * 4.0) * 0.3) * yPos - uYOffset;
    return 1.0 - smoothstep(thickness, thickness + softness, abs(uv.y - y));
  }

  void main() {
    vec2 uv = gl_FragCoord.xy / iResolution.y;
    vec4 col = vec4(0.0, 0.0, 0.0, 1.0);
    col.xyz = mix(uBgColor1, uBgColor2, uv.x + uv.y);
    uv -= 0.5;
    float aaDy = iResolution.y * 0.000005;

    for (float i = 0.; i < MAX_LINES; i += 1.) {
      if (i <= uLineCount) {
        float t = i / (uLineCount - 1.0);
        vec3 lineCol = mix(uLineColor1, uLineColor2, t);

        float bokeh = pow(t, 2.0);
        float thickness = 0.0015;
        float softness = aaDy + bokeh * 0.03;

        float amp = uAmplitude - 0.03 * t;
        float amt = max(0.0, pow(1.0 - bokeh, 1.5) * 0.85);

        float lineWeight = wave(uv, uSpeed * (1.0 + t * 0.5), amp, thickness, softness) * amt;

        if (uThemeMode > 0.5) {
          col.xyz += lineCol * lineWeight;
        } else {
          col.xyz = mix(col.xyz, lineCol, lineWeight);
        }
      }
    }

    gl_FragColor = col;
  }
`;

const UNIFORM_NAMES = [
  'iResolution', 'iTime', 'uSpeed', 'uLineCount',
  'uAmplitude', 'uYOffset', 'uThemeMode',
  'uBgColor1', 'uBgColor2', 'uLineColor1', 'uLineColor2',
] as const;

type Uniforms = Record<(typeof UNIFORM_NAMES)[number], WebGLUniformLocation | null>;

function compileShader(gl: WebGLRenderingContext, type: number, source: string): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function initWebGL(canvas: HTMLCanvasElement): { gl: WebGLRenderingContext; program: WebGLProgram; uniforms: Uniforms } | null {
  const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl') as WebGLRenderingContext | null;
  if (!gl) return null;

  const vs = compileShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER);
  const fs = compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
  if (!vs || !fs) return null;

  const program = gl.createProgram()!;
  gl.attachShader(program, vs);
  gl.attachShader(program, fs);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return null;

  gl.useProgram(program);

  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]), gl.STATIC_DRAW);

  const pos = gl.getAttribLocation(program, 'a_position');
  gl.enableVertexAttribArray(pos);
  gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0);

  const uniforms = {} as Uniforms;
  for (const name of UNIFORM_NAMES) {
    uniforms[name] = gl.getUniformLocation(program, name);
  }

  return { gl, program, uniforms };
}

export const VantaBackground: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);
  const startRef = useRef(Date.now());
  const ctxRef = useRef<{ gl: WebGLRenderingContext; uniforms: Uniforms } | null>(null);
  const { isDark } = useTheme();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const result = initWebGL(canvas);
    if (!result) return;

    const { gl, uniforms } = result;
    ctxRef.current = { gl, uniforms };
    startRef.current = Date.now();

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        gl.viewport(0, 0, canvas.width, canvas.height);
      }
    };

    const render = () => {
      resize();
      const t = (Date.now() - startRef.current) / 1000;
      gl.uniform2f(uniforms.iResolution, canvas.width, canvas.height);
      gl.uniform1f(uniforms.iTime, t);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      rafRef.current = requestAnimationFrame(render);
    };

    gl.uniform1f(uniforms.uSpeed, 0.4);
    gl.uniform1f(uniforms.uLineCount, 12);
    gl.uniform1f(uniforms.uAmplitude, 0.20);
    gl.uniform1f(uniforms.uYOffset, 0.00);

    render();
    window.addEventListener('resize', resize);

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(rafRef.current);
    };
  }, []);

  useEffect(() => {
    const ctx = ctxRef.current;
    if (!ctx) return;
    const { gl, uniforms } = ctx;
    const t = isDark ? THEMES.dark : THEMES.light;

    gl.uniform1f(uniforms.uThemeMode, t.mode);
    gl.uniform3fv(uniforms.uBgColor1, t.bg1 as unknown as Float32List);
    gl.uniform3fv(uniforms.uBgColor2, t.bg2 as unknown as Float32List);
    gl.uniform3fv(uniforms.uLineColor1, t.line1 as unknown as Float32List);
    gl.uniform3fv(uniforms.uLineColor2, t.line2 as unknown as Float32List);
  }, [isDark]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100vh',
        zIndex: 0,
        pointerEvents: 'none',
        display: 'block',
      }}
    />
  );
};
