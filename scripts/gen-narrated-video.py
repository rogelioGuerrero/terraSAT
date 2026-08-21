"""Genera video narrado profesional con TTS + clips de TerraSAT.

Efectos cinematográficos:
- Fade in desde negro (1s) al inicio
- Fade out a negro (1.5s) al final
- Transiciones fade-through-black entre clips (0.5s)
- Branding overlay TerraSAT (logo + agtisa.com)
- Audio narrado con edge-tts
- Video se corta a la duración del audio
"""
import asyncio
import subprocess
import os
import re
import tempfile
from pathlib import Path

import edge_tts

BASE = Path(__file__).parent.parent
ASSETS = BASE / "web" / "src" / "assets"
OUTPUT = BASE / "scripts" / "forest-narrated-video.mp4"
TTS_OUTPUT = BASE / "scripts" / "forest-narration.mp3"
OVERLAY_PNG = BASE / "scripts" / "overlay-terrasat.png"
INTRO_MP4 = BASE / "scripts" / ".cards" / "intro.mp4"
OUTRO_MP4 = BASE / "scripts" / ".cards" / "cta.mp4"

# Configuración video
WIDTH = 1280
HEIGHT = 720
FPS = 24
CRF = 23
FADE_IN_DUR = 1.0       # Fade in inicial desde negro
FADE_OUT_DUR = 1.5      # Fade out final a negro
CLIP_FADE_DUR = 0.5     # Fade entre clips (through black)

# Voz latino neutra
VOICE = "es-US-AlonsoNeural"

# Narración del artículo de ForestSAT
NARRATION = (
    "Lo que el satélite ve cuando el bosque desaparece. "
    "Consultamos imágenes de Sentinel-2 de la Agencia Espacial Europea entre agosto de 2025 y junio de 2026 "
    "en 10 zonas forestales de 8 países de Latinoamérica. "
    "Calculamos NDVI e NBR para cada zona. "
    "Tres zonas muestran una señal doble de deforestación y quema simultánea, "
    "algo que solo se ve cuando el bosque está siendo eliminado activamente. "
    "\n\n"
    "El Chaco paraguayo registró la caída más profunda: NDVI cayó 0.394 y NBR se desplomó 0.297. "
    "Es la señal más severa de las 10 zonas analizadas. "
    "La combinación de pérdida de vegetación y caída del NBR apunta a tala seguida de quema, "
    "el patrón clásico de expansión ganadera en el Chaco. "
    "\n\n"
    "Leticia, en la frontera amazónica de Colombia, muestra el mismo patrón: "
    "NDVI menos 0.362 y NBR menos 0.305. "
    "El Ideam reportó que la deforestación nacional subió 5.2 por ciento en 2025, "
    "con 72 mil hectáreas perdidas en la Amazonía colombiana. "
    "El satélite de la ESA confirma lo que Ideam detectó desde el suelo. "
    "\n\n"
    "Darién, en Panamá, presenta la tercera señal doble. "
    "Pero aquí hay una historia más compleja. "
    "Global Forest Watch documentó que la pérdida de bosque en el Parque Nacional Darién se redujo 88 por ciento "
    "entre 2022 y 2025, gracias a guardaparques equipados con alertas satelitales. "
    "La presión se desplazó hacia el buffer. "
    "\n\n"
    "Pero no todo es pérdida. "
    "Manaus, en el corazón del Amazonas brasileño, mostró recuperación: "
    "NDVI más 0.202 y NBR más 0.157. "
    "MapBiomas confirmó que Brasil redujo su deforestación 20 por ciento en 2025. "
    "\n\n"
    "El Observatorio Regional Amazónico reportó que la deforestación cayó 68 por ciento en 2025. "
    "Pero MAAP estimó que aún se deforestaron 736 mil hectáreas, "
    "con 132 mil dentro de áreas protegidas y territorios indígenas. "
    "La reducción es real, pero el problema estructural persiste. "
    "\n\n"
    "ForestSAT detecta pérdida de cobertura, áreas quemadas y degradación forestal "
    "con datos de Sentinel-2 de la ESA. "
    "Reportes personalizados por zona y monitoreo continuo."
)

# Videos de ForestSAT
CLIPS = [
    ASSETS / "informe-forest-video-opt.mp4",
    ASSETS / "informe-coffee-hill-video-opt.mp4",
    ASSETS / "informe-soybean-video-opt.mp4",
    ASSETS / "informe-coffee-video-opt.mp4",
]

FFMPEG = str(BASE / "node_modules" / "ffmpeg-static" / "ffmpeg.exe")
if not Path(FFMPEG).exists():
    FFMPEG = "ffmpeg"

NODE = "node"


def run(cmd, **kwargs):
    """Ejecuta comando y muestra errores si falla."""
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print(f"  ERROR: {' '.join(str(c) for c in cmd[:3])}...")
        if result.stderr:
            print(f"  stderr: {result.stderr[-500:]}")
    return result


def get_duration(filepath):
    """Obtiene duración de un archivo con ffmpeg."""
    result = subprocess.run(
        [FFMPEG, "-i", str(filepath), "-f", "null", "-"],
        capture_output=True, text=True
    )
    for line in result.stderr.split("\n"):
        m = re.search(r"Duration:\s+(\d+):(\d+):(\d+\.\d+)", line)
        if m:
            h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            return h * 3600 + mn * 60 + s
    return 0


async def generate_tts():
    """Genera narración con edge-tts."""
    print(f"[1/5] Generando narración TTS (voz: {VOICE})...")
    communicate = edge_tts.Communicate(NARRATION, VOICE)
    await communicate.save(str(TTS_OUTPUT))
    print(f"      Audio: {TTS_OUTPUT.name} ({get_duration(TTS_OUTPUT):.1f}s)")


def generate_overlay():
    """Genera PNG de branding TerraSAT con sharp."""
    print("[2/5] Generando overlay de branding TerraSAT...")
    script = BASE / "scripts" / "gen-overlay-terrasat.mjs"
    result = run([NODE, str(script), "--width", str(WIDTH), "--height", str(HEIGHT),
                  "--output", str(OVERLAY_PNG)], cwd=str(BASE))
    if result.returncode == 0:
        print(f"      Overlay: {OVERLAY_PNG.name}")
    else:
        print("      WARNING: no se pudo generar overlay, continuando sin branding")
    return OVERLAY_PNG.exists()


def process_clip_v2(input_path, output_path, overlay_path, is_first, is_last, total_clips):
    """Procesa un clip: escala, pad, overlay branding, fade in/out."""
    dur = get_duration(input_path)
    if dur <= 0:
        raise ValueError(f"Sin duración: {input_path}")

    # Fade in: largo en el primer clip, corto en el resto (transición through-black)
    fade_filters = []
    if is_first:
        fade_filters.append(f"fade=t=in:st=0:d={FADE_IN_DUR}")
    else:
        fade_filters.append(f"fade=t=in:st=0:d={CLIP_FADE_DUR}")

    # Fade out: largo en el último clip, corto en el resto (transición through-black)
    if is_last:
        fade_out_start = max(0, dur - FADE_OUT_DUR)
        fade_filters.append(f"fade=t=out:st={fade_out_start:.3f}:d={FADE_OUT_DUR}")
    else:
        fade_out_start = max(0, dur - CLIP_FADE_DUR)
        fade_filters.append(f"fade=t=out:st={fade_out_start:.3f}:d={CLIP_FADE_DUR}")

    fade_chain = ",".join(fade_filters)

    # Construir filter_complex
    if overlay_path and Path(overlay_path).exists():
        filter_complex = (
            f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black[base];"
            f"[base][1:v]overlay=0:0:format=auto,format=yuv420p,fps={FPS},{fade_chain}[v]"
        )
        cmd = [
            FFMPEG, "-y",
            "-i", str(input_path),
            "-i", str(overlay_path),
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(CRF),
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-movflags", "+faststart",
            str(output_path)
        ]
    else:
        filter_v = (
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"format=yuv420p,fps={FPS},{fade_chain}"
        )
        cmd = [
            FFMPEG, "-y",
            "-i", str(input_path),
            "-vf", filter_v,
            "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(CRF),
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-movflags", "+faststart",
            str(output_path)
        ]

    run(cmd)


def build_video():
    """Procesa clips con branding + fades, concatena, y mezcla con narración."""
    audio_dur = get_duration(TTS_OUTPUT)
    print(f"      Narración: {audio_dur:.1f}s")

    # Crear directorio temporal
    tmp_dir = Path(tempfile.mkdtemp(prefix="terrasat_video_"))

    # Calcular cuántos clips necesitamos para cubrir el audio
    # Si los clips no alcanzan, se repiten en orden
    clip_durs = [get_duration(c) for c in CLIPS]
    single_pass_dur = sum(clip_durs)

    # Determinar secuencia de clips (con repetición si es necesario)
    clip_sequence = []
    total_dur = 0
    round_num = 0
    while total_dur < audio_dur + 2:
        for i, clip in enumerate(CLIPS):
            if total_dur >= audio_dur + 2:
                break
            clip_sequence.append((clip, i))
            total_dur += clip_durs[i]
        round_num += 1
        if round_num > 10:
            break

    print(f"[3/5] Procesando {len(clip_sequence)} clips ({round_num} pasada(s)) con branding + fades...")
    processed_clips = []
    total_dur = 0
    for idx, (clip, original_i) in enumerate(clip_sequence):
        clip_dur = clip_durs[original_i]
        is_last = (idx == len(clip_sequence) - 1)
        print(f"      Clip {idx+1}/{len(clip_sequence)}: {clip.name} ({clip_dur:.1f}s){' [repetido]' if idx >= len(CLIPS) else ''}")

        out = tmp_dir / f"clip_{idx:02d}.mp4"
        # Pasar is_last como flag para el fade out final
        process_clip_v2(clip, out, OVERLAY_PNG, idx == 0, is_last, len(clip_sequence))
        processed_clips.append(out)
        total_dur += clip_dur

    print(f"      Total video: {total_dur:.1f}s (audio: {audio_dur:.1f}s)")

    print("[4/5] Concatenando intro + clips + outro...")
    concat_list = tmp_dir / "concat.txt"
    with open(concat_list, "w") as f:
        # Intro (sin audio, con sus propios fades)
        if INTRO_MP4.exists():
            f.write(f"file '{INTRO_MP4.absolute()}'\n")
        for clip in processed_clips:
            f.write(f"file '{clip.absolute()}'\n")
        # Outro CTA (sin audio, con sus propios fades)
        if OUTRO_MP4.exists():
            f.write(f"file '{OUTRO_MP4.absolute()}'\n")

    concat_output = tmp_dir / "concat.mp4"
    # Re-encode durante concat (no copy) para evitar incompatibilidad de codecs
    # entre cards (libx264 crf 20) y clips procesados (libx264 crf 23)
    run([
        FFMPEG, "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(CRF),
        "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        "-an",
        "-movflags", "+faststart",
        str(concat_output)
    ])

    print("[5/5] Mezclando video + narración...")
    # El audio empieza después del intro (2s)
    # Duración total = intro + audio + outro
    intro_dur = get_duration(INTRO_MP4) if INTRO_MP4.exists() else 0
    outro_dur = get_duration(OUTRO_MP4) if OUTRO_MP4.exists() else 0
    total_target = intro_dur + audio_dur + outro_dur

    run([
        FFMPEG, "-y",
        "-i", str(concat_output),
        "-i", str(TTS_OUTPUT),
        "-filter_complex",
        f"[1:a]adelay={int(intro_dur * 1000)}|{int(intro_dur * 1000)}[a]",
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-t", f"{total_target:.3f}",
        "-movflags", "+faststart",
        str(OUTPUT)
    ])

    # Limpiar temporales
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)

    final_dur = get_duration(OUTPUT)
    size_mb = OUTPUT.stat().st_size / (1024 * 1024)
    print(f"\n✅ Video creado: {OUTPUT}")
    print(f"   Duración: {final_dur:.1f}s | Tamaño: {size_mb:.1f}MB")
    print(f"   Estructura: Intro {intro_dur:.0f}s → Clips narrados {audio_dur:.0f}s → CTA {outro_dur:.0f}s")
    print(f"   Efectos: fade in {FADE_IN_DUR}s, fade out {FADE_OUT_DUR}s, transiciones {CLIP_FADE_DUR}s")
    print(f"   Branding: TerraSAT + agtisa.com")


async def main():
    await generate_tts()
    has_overlay = generate_overlay()
    if has_overlay:
        print("      Branding: activado")
    build_video()

if __name__ == "__main__":
    asyncio.run(main())
