"""Sandbox cinematográfico TerraSAT — Conversatorio parametrizable.

Genera un conversatorio con 2 o 3 voces, interrupciones, solapamientos,
microvacilaciones y branding TerraSAT. Video real con clips de Pexels.

Uso:
  python scripts/gen-conversatorio.py                            # 3 voces, guion hardcoded
  python scripts/gen-conversatorio.py --article scripts/agro-article.txt  # guion auto con Groq
  python scripts/gen-conversatorio.py --voices 2         # 2 voces (style NotebookLM)
  python scripts/gen-conversatorio.py --clips agrosat,coffee,soybean
  python scripts/gen-conversatorio.py --output mi-video.mp4
"""
import argparse
import asyncio
import subprocess
import re
import tempfile
import shutil
import json
import os
from pathlib import Path

import edge_tts
from dotenv import load_dotenv

BASE = Path(__file__).parent.parent
ASSETS = BASE / "web" / "src" / "assets"

load_dotenv()

GROQ_MODEL = os.getenv("NOOA_MODEL", "groq/openai/gpt-oss-120b")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
DEFAULT_OUTPUT = BASE / "scripts" / "demo-conversatorio.mp4"
OVERLAY_PNG = BASE / "scripts" / "overlay-terrasat.png"
INTRO_MP4 = BASE / "scripts" / ".cards" / "intro.mp4"
OUTRO_MP4 = BASE / "scripts" / ".cards" / "cta.mp4"

WIDTH = 1280
HEIGHT = 720
FPS = 24
CRF = 23
FADE_IN_DUR = 1.0
FADE_OUT_DUR = 1.5
CLIP_FADE_DUR = 0.5

# Voces con rate/pitch para entonación variada
VOICES = {
    "MODERADOR": {"voice": "es-US-AlonsoNeural", "rate": "-3%", "pitch": "-1Hz"},   # Pausado, grave
    "EXPERTA":   {"voice": "es-US-PalomaNeural",  "rate": "+2%", "pitch": "+1Hz"},   # Ágil, natural
    "ANALISTA":  {"voice": "es-MX-JorgeNeural",  "rate": "-5%", "pitch": "-3Hz"},   # Grave, reflexivo
}

FFMPEG = str(BASE / "node_modules" / "ffmpeg-static" / "ffmpeg.exe")
if not Path(FFMPEG).exists():
    FFMPEG = "ffmpeg"

# ── GUION de respaldo (cuando no se usa --article) ──
# Cada línea: (personaje, texto, tipo)
# tipo: "normal" | "interrumpe" | "solapa" | "asentimiento" (respuesta corta rápida)
# "..." en el texto genera microvacilaciones naturales en edge-tts
# "—" al final indica que el personaje fue interrumpido

GUION_FALLBACK = [
    ("MODERADOR", "Bienvenidos a TerraSAT Reportes. Hoy... la verdad es que el dato nos sorprendió. La sequía está golpeando cultivos en toda Latinoamérica.", "normal"),
    ("EXPERTA", "Y no es una sequía cualquiera, ¿eh? Café, soja y viñas... todo al mismo tiempo.", "solapa"),
    ("ANALISTA", "O sea, ¿esto no es un país puntual, es un patrón regional?", "normal"),
    ("EXPERTA", "Exacto. Mira, en Honduras... Intibucá y El Paraíso, sequía severa. Más de 25 mil hectáreas de café.", "normal"),
    ("MODERADOR", "25 mil hectáreas, eso es—", "interrumpe"),
    ("EXPERTA", "—Es muchísimo. Pero espera... Brasil es peor. Mato Grosso, sequía severa, más de 139 mil hectáreas de soja.", "interrumpe"),
    ("ANALISTA", "Momento... ¿139 mil? ¿Y eso es solo soja o incluye otros cultivos?", "normal"),
    ("EXPERTA", "Solo soja. En Espíritu Santo, sequía moderada en café. Y en Colombia, Caldas también con sequía moderada en café.", "normal"),
    ("ANALISTA", "Claro... entonces el patrón es transfronterizo. Honduras, Brasil, Colombia...", "normal"),
    ("MODERADOR", "¿Y cómo lo detectan ustedes antes que los demás?", "normal"),
    ("EXPERTA", "Nuestro sistema detecta esto 15 días antes de que aparezcan síntomas visibles.", "normal"),
    ("ANALISTA", "¿15 días? ¿Cómo... cómo es eso posible técnicamente?", "normal"),
    ("EXPERTA", "Usamos imágenes satelitales de NASA y ESA. El estrés hídrico se ve en el infrarrojo... antes de que la hoja se ponga amarilla.", "normal"),
    ("ANALISTA", "Ah, o sea que la planta ya está sufriendo antes de que se note a simple vista.", "asentimiento"),
    ("EXPERTA", "Así es. Y hay zonas bajo vigilancia... Jinotega en Nicaragua, Valle Central en Chile. Sequía leve, pero hay que monitorear.", "normal"),
    ("MODERADOR", "¿Y zonas normales? Para no alarmar de más...", "normal"),
    ("EXPERTA", "Claro. Córdoba y Mendoza en Argentina, São Paulo en Brasil. Sin sequía. Pero eso no significa que no puedan—", "interrumpe"),
    ("ANALISTA", "—Que no puedan cambiar. Claro. La pregunta clave es: ¿su plantación está en alguna de estas zonas?", "interrumpe"),
    ("EXPERTA", "Exactamente. AgroSAT da reportes personalizados. La información está... la pregunta es si la usamos a tiempo.", "normal"),
    ("MODERADOR", "Ver antes es decidir mejor. Gracias por acompañarnos en TerraSAT Reportes.", "normal"),
]

# Catálogo de clips disponibles
CLIPS_CATALOG = {
    "agrosat":  ASSETS / "informe-agrosat-crisis-video-opt.mp4",
    "coffee":   ASSETS / "informe-coffee-video-opt.mp4",
    "hill":     ASSETS / "informe-coffee-hill-video-opt.mp4",
    "soybean":  ASSETS / "informe-soybean-video-opt.mp4",
}

DEFAULT_CLIPS = ["agrosat", "hill", "soybean", "coffee"]


# ── Generación de guion con Groq ──

GUION_SYSTEM_PROMPT = """Eres un guionista profesional de podcasts de divulgación científica en español.
Tu tarea es convertir un informe técnico en un guion de conversatorio natural entre 3 personajes.

Personajes:
- MODERADOR: Conduce, hace preguntas grandes, introduce temas. Tono pausado y accesible.
- EXPERTA: Aporta datos técnicos precisos del informe. Tono ágil y directo.
- ANALISTA: Cuestiona, pide aclaraciones, aporta contexto regional. Tono reflexivo.

Reglas de naturalidad:
- Usa "..." para microvacilaciones (pausas cortas naturales)
- Usa expresiones coloquiales: "Mira...", "O sea...", "Momento...", "¿eh?", "Claro", "Así es"
- Los personajes se interrumpen entre sí. Cuando un personaje es interrumpido, termina su texto con "—"
- El personaje que interrumpe empieza con "—" si viene de una interrupción
- NO inventes datos que no estén en el informe
- NO incluyas contacto ni CTA en el diálogo (eso va en el outro visual)
- Mantén el diálogo en 15-22 líneas, duración objetivo 2-3 minutos

Tipos de línea:
- "normal": diálogo regular
- "interrumpe": el personaje corta al anterior (el anterior termina con "—")
- "solapa": el personaje empieza a hablar antes de que termine el anterior
- "asentimiento": respuesta corta rápida ("Claro", "Así es", "Ah, o sea...")

Estructura narrativa:
1. Gancho inicial (MODERADOR presenta el tema con intriga)
2. Datos clave (EXPERTA comparte cifras del informe)
3. Análisis y cuestionamiento (ANALISTA pregunta, EXPERTA responde)
4. Síntesis (cierre con reflexión, sin CTA)

Responde SOLO con un JSON array. Cada elemento debe tener:
{"personaje": "MODERADOR|EXPERTA|ANALISTA", "texto": "...", "tipo": "normal|interrumpe|solapa|asentimiento"}

No incluyas markdown, no incluyas explicaciones, SOLO el JSON array."""


def generate_guion_with_groq(article_text, num_voices=3):
    """Genera el guion del conversatorio usando Groq desde el texto del artículo."""
    from litellm import completion

    characters_desc = "3 personajes: MODERADOR, EXPERTA y ANALISTA"
    if num_voices == 2:
        characters_desc = "2 personajes: MODERADOR y EXPERTA (sin ANALISTA)"

    user_prompt = f"""Convierte el siguiente informe en un guion de conversatorio con {characters_desc}.

INFORME:
{article_text}

Genera el JSON array con el guion. Recuerda: SOLO JSON, sin markdown."""

    print(f"  Llamando a Groq ({GROQ_MODEL})...")
    response = completion(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": GUION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=4000,
        timeout=90,
    )

    raw = response.choices[0].message.content.strip()

    # Debug: mostrar los primeros 200 chars de la respuesta
    print(f"  Respuesta raw ({len(raw)} chars): {raw[:200]}...")

    # Limpiar markdown si lo hubiera
    if raw.startswith("```"):
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
    raw = raw.strip()

    # Intentar parsear directamente
    guion_data = None
    try:
        guion_data = json.loads(raw)
    except json.JSONDecodeError:
        # Extraer array JSON balanceando brackets
        start = raw.find('[')
        if start >= 0:
            depth = 0
            in_string = False
            escape = False
            for i in range(start, len(raw)):
                c = raw[i]
                if escape:
                    escape = False
                    continue
                if c == '\\':
                    escape = True
                    continue
                if c == '"' and not escape:
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if c == '[':
                    depth += 1
                elif c == ']':
                    depth -= 1
                    if depth == 0:
                        try:
                            guion_data = json.loads(raw[start:i+1])
                        except json.JSONDecodeError:
                            pass
                        break

    # Si aún no funciona, intentar con reasoning
    if guion_data is None:
        reasoning = getattr(response.choices[0].message, "reasoning", None) or ""
        if reasoning:
            print(f"  Intentando con reasoning ({len(reasoning)} chars)...")
            print(f"  Reasoning preview: {reasoning[:300]}...")
            start = reasoning.find('[')
            if start >= 0:
                depth = 0
                in_string = False
                escape = False
                for i in range(start, len(reasoning)):
                    c = reasoning[i]
                    if escape:
                        escape = False
                        continue
                    if c == '\\':
                        escape = True
                        continue
                    if c == '"' and not escape:
                        in_string = not in_string
                        continue
                    if in_string:
                        continue
                    if c == '[':
                        depth += 1
                    elif c == ']':
                        depth -= 1
                        if depth == 0:
                            try:
                                guion_data = json.loads(reasoning[start:i+1])
                            except json.JSONDecodeError:
                                pass
                            break

    if guion_data is None:
        raise ValueError(f"No se pudo extraer JSON del response. Raw: {raw[:300]}")

    # Convertir a formato de tuplas
    guion = []
    for item in guion_data:
        personaje = item.get("personaje", "MODERADOR").upper()
        if num_voices == 2 and personaje == "ANALISTA":
            personaje = "MODERADOR"
        texto = item.get("texto", "")
        tipo = item.get("tipo", "normal")
        guion.append((personaje, texto, tipo))

    return guion


def run(cmd, **kwargs):
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        print(f"  ERROR: {' '.join(str(c) for c in cmd[:3])}...")
        if result.stderr:
            print(f"  stderr: {result.stderr[-500:]}")
    return result


def get_duration(filepath):
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


def filter_guion(guion, num_voices):
    """Filtra el guion según el número de voces. Si num_voices=2, elimina ANALISTA."""
    if num_voices >= 3:
        return guion
    # Con 2 voces, reasignar líneas del ANALISTA al MODERADOR
    filtered = []
    for personaje, texto, tipo in guion:
        if personaje == "ANALISTA":
            personaje = "MODERADOR"
        filtered.append((personaje, texto, tipo))
    return filtered


async def generate_voice_segments(guion, tmp_dir):
    """Genera cada línea del guion como MP3 separado con la voz y entonación del personaje."""
    segments = []
    for i, (personaje, texto, tipo) in enumerate(guion):
        cfg = VOICES[personaje]
        voz = cfg["voice"]
        rate = cfg.get("rate", "+0%")
        pitch = cfg.get("pitch", "+0Hz")

        mp3_path = tmp_dir / f"seg_{i:03d}.mp3"
        communicate = edge_tts.Communicate(texto, voz, rate=rate, pitch=pitch)
        await communicate.save(str(mp3_path))
        dur = get_duration(mp3_path)

        # Si termina con — (interrupción), cortar el último 20% del audio
        if texto.rstrip().endswith("—"):
            cut_dur = dur * 0.80
            cut_path = tmp_dir / f"seg_{i:03d}_cut.mp3"
            run([FFMPEG, "-y", "-i", str(mp3_path), "-t", f"{cut_dur:.3f}",
                 "-c", "copy", str(cut_path)])
            mp3_path = cut_path
            dur = get_duration(cut_path)

        segments.append({
            "index": i,
            "personaje": personaje,
            "tipo": tipo,
            "mp3": mp3_path,
            "dur": dur,
        })
        print(f"  [{i+1}/{len(guion)}] {personaje} ({tipo}): {dur:.1f}s")

    return segments


def concat_audio_segments(segments, tmp_dir):
    """Concatena los segmentos de audio con solapamiento donde corresponda."""
    print("  Concatenando audio con solapamientos...")

    # Estrategia: para "solapa", mezclar el final del segmento anterior
    # con el inicio del siguiente (overlap de 0.3s)
    # Para "interrumpe", el segmento anterior ya está cortado,
    # y el nuevo empieza inmediatamente

    OVERLAP_DUR = 0.2  # segundos de solapamiento (reducido)

    # Procesar segmento por segmento, ajustando timestamps
    # Método simple: concatenar con pequeño silencio entre normales,
    # sin silencio en interrupciones, y crossfade en solapamientos

    current_audio = segments[0]["mp3"]
    current_dur = segments[0]["dur"]

    for i in range(1, len(segments)):
        seg = segments[i]
        next_audio = seg["mp3"]
        next_dur = seg["dur"]
        combined = tmp_dir / f"combined_{i:03d}.mp3"

        if seg["tipo"] == "solapa":
            # Crossfade: los últimos 0.3s del actual se mezclan con los primeros 0.3s del siguiente
            crossfade = min(OVERLAP_DUR, current_dur * 0.3, next_dur * 0.3)
            run([
                FFMPEG, "-y",
                "-i", str(current_audio),
                "-i", str(next_audio),
                "-filter_complex",
                f"[0:a][1:a]acrossfade=d={crossfade:.3f}:c1=tri:c2=tri[a]",
                "-map", "[a]",
                "-c:a", "libmp3lame", "-b:a", "128k",
                str(combined)
            ])
            current_dur = current_dur + next_dur - crossfade

        elif seg["tipo"] == "interrumpe":
            # Sin pausa, concatenación directa
            list_file = tmp_dir / f"list_{i:03d}.txt"
            with open(list_file, "w") as f:
                f.write(f"file '{current_audio.absolute()}'\n")
                f.write(f"file '{next_audio.absolute()}'\n")
            run([
                FFMPEG, "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c:a", "libmp3lame", "-b:a", "128k",
                str(combined)
            ])
            current_dur = current_dur + next_dur
            list_file.unlink(missing_ok=True)

        elif seg["tipo"] == "asentimiento":
            # Asentimiento: sin silencio, concatenación directa (respuesta rápida)
            list_file = tmp_dir / f"list_{i:03d}.txt"
            with open(list_file, "w") as f:
                f.write(f"file '{current_audio.absolute()}'\n")
                f.write(f"file '{next_audio.absolute()}'\n")
            run([
                FFMPEG, "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c:a", "libmp3lame", "-b:a", "128k",
                str(combined)
            ])
            current_dur = current_dur + next_dur
            list_file.unlink(missing_ok=True)

        else:
            # Normal: 0.15s de silencio entre segmentos (reducido de 0.4s)
            silence = tmp_dir / f"silence_{i:03d}.mp3"
            run([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
                 "-t", "0.15", "-c:a", "libmp3lame", "-b:a", "128k", str(silence)])

            list_file = tmp_dir / f"list_{i:03d}.txt"
            with open(list_file, "w") as f:
                f.write(f"file '{current_audio.absolute()}'\n")
                f.write(f"file '{silence.absolute()}'\n")
                f.write(f"file '{next_audio.absolute()}'\n")
            run([
                FFMPEG, "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c:a", "libmp3lame", "-b:a", "128k",
                str(combined)
            ])
            current_dur = current_dur + 0.15 + next_dur
            list_file.unlink(missing_ok=True)
            silence.unlink(missing_ok=True)

        current_audio = combined

    # Convertir a MP3 final
    final_audio = tmp_dir / "narration_full.mp3"
    shutil.copy(current_audio, final_audio)
    return final_audio


def process_clip_v2(input_path, output_path, overlay_path, is_first, is_last, total_clips):
    """Procesa un clip: escala, pad, overlay branding, fade in/out."""
    dur = get_duration(input_path)
    if dur <= 0:
        raise ValueError(f"Sin duración: {input_path}")

    fade_filters = []
    if is_first:
        fade_filters.append(f"fade=t=in:st=0:d={FADE_IN_DUR}")
    else:
        fade_filters.append(f"fade=t=in:st=0:d={CLIP_FADE_DUR}")

    if is_last:
        fade_out_start = max(0, dur - FADE_OUT_DUR)
        fade_filters.append(f"fade=t=out:st={fade_out_start:.3f}:d={FADE_OUT_DUR}")
    else:
        fade_out_start = max(0, dur - CLIP_FADE_DUR)
        fade_filters.append(f"fade=t=out:st={fade_out_start:.3f}:d={CLIP_FADE_DUR}")

    fade_chain = ",".join(fade_filters)

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


def build_video(audio_path, clips, output_path, tmp_dir):
    """Construye el video completo con intro + clips + outro + audio del conversatorio."""
    audio_dur = get_duration(audio_path)
    print(f"      Audio conversatorio: {audio_dur:.1f}s")

    # Calcular clips necesarios
    clip_durs = [get_duration(c) for c in clips]
    clip_sequence = []
    total_dur = 0
    round_num = 0
    while total_dur < audio_dur + 2:
        for i, clip in enumerate(clips):
            if total_dur >= audio_dur + 2:
                break
            clip_sequence.append((clip, i))
            total_dur += clip_durs[i]
        round_num += 1
        if round_num > 10:
            break

    print(f"  Procesando {len(clip_sequence)} clips ({round_num} pasada(s))...")
    processed_clips = []
    total_dur = 0
    for idx, (clip, original_i) in enumerate(clip_sequence):
        clip_dur = clip_durs[original_i]
        is_last = (idx == len(clip_sequence) - 1)
        print(f"    Clip {idx+1}/{len(clip_sequence)}: {clip.name} ({clip_dur:.1f}s)")
        out = tmp_dir / f"clip_{idx:02d}.mp4"
        process_clip_v2(clip, out, OVERLAY_PNG, idx == 0, is_last, len(clip_sequence))
        processed_clips.append(out)
        total_dur += clip_dur

    print(f"  Concatenando intro + clips + outro...")
    concat_list = tmp_dir / "concat.txt"
    with open(concat_list, "w") as f:
        if INTRO_MP4.exists():
            f.write(f"file '{INTRO_MP4.absolute()}'\n")
        for clip in processed_clips:
            f.write(f"file '{clip.absolute()}'\n")
        if OUTRO_MP4.exists():
            f.write(f"file '{OUTRO_MP4.absolute()}'\n")

    concat_output = tmp_dir / "concat.mp4"
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

    print(f"  Mezclando video + audio conversatorio...")
    intro_dur = get_duration(INTRO_MP4) if INTRO_MP4.exists() else 0
    outro_dur = get_duration(OUTRO_MP4) if OUTRO_MP4.exists() else 0
    total_target = intro_dur + audio_dur + outro_dur

    run([
        FFMPEG, "-y",
        "-i", str(concat_output),
        "-i", str(audio_path),
        "-filter_complex",
        f"[1:a]adelay={int(intro_dur * 1000)}|{int(intro_dur * 1000)}[a]",
        "-map", "0:v",
        "-map", "[a]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k",
        "-t", f"{total_target:.3f}",
        "-movflags", "+faststart",
        str(output_path)
    ])

    final_dur = get_duration(output_path)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\n✅ Conversatorio creado: {output_path}")
    print(f"   Duración: {final_dur:.1f}s | Tamaño: {size_mb:.1f}MB")
    print(f"   Estructura: Intro {intro_dur:.0f}s → Conversatorio {audio_dur:.0f}s → CTA {outro_dur:.0f}s")
    print(f"   Voces: Moderador ({VOICES['MODERADOR']['voice']}) + Experta ({VOICES['EXPERTA']['voice']}) + Analista ({VOICES['ANALISTA']['voice']})")
    print(f"   Técnicas: interrupciones, solapamientos, asentimientos, microvacilaciones, entonación por personaje")


async def main():
    parser = argparse.ArgumentParser(description="Conversatorio cinematográfico TerraSAT")
    parser.add_argument("--voices", type=int, choices=[2, 3], default=3,
                        help="Número de voces (2=NotebookLM style, 3=nuestro plus)")
    parser.add_argument("--clips", type=str, default=",".join(DEFAULT_CLIPS),
                        help="Clips separados por coma: agrosat,hill,soybean,coffee")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT),
                        help="Ruta de salida del MP4")
    parser.add_argument("--article", type=str, default=None,
                        help="Archivo .txt del informe para auto-generar guion con Groq")
    args = parser.parse_args()

    # Resolver clips
    clip_names = [c.strip() for c in args.clips.split(",")]
    clips = []
    for name in clip_names:
        if name in CLIPS_CATALOG and CLIPS_CATALOG[name].exists():
            clips.append(CLIPS_CATALOG[name])
        else:
            print(f"  ⚠ Clip no encontrado: {name}")
    if not clips:
        print("  ✗ Sin clips válidos. Abortando.")
        return

    output_path = Path(args.output)

    # Generar o usar guion de respaldo
    if args.article:
        article_path = Path(args.article)
        if not article_path.exists():
            print(f"  ✗ Artículo no encontrado: {article_path}")
            return
        article_text = article_path.read_text(encoding="utf-8")
        print("=" * 60)
        print(f"  CONVERSATORIO TerraSAT — {args.voices} voces (guion auto)")
        print("=" * 60)
        print(f"  Artículo: {article_path.name}")
        print(f"  Clips: {', '.join(c.name for c in clips)}")
        print(f"  Output: {output_path}")
        print(f"\n[0/5] Generando guion con Groq...")
        guion = generate_guion_with_groq(article_text, args.voices)
        print(f"      Guion generado: {len(guion)} líneas")
        for i, (p, t, tipo) in enumerate(guion):
            print(f"      [{i+1}] {p} ({tipo}): {t[:60]}...")
    else:
        guion = filter_guion(GUION_FALLBACK, args.voices)
        print("=" * 60)
        print(f"  CONVERSATORIO TerraSAT — {args.voices} voces (guion de respaldo)")
        print("=" * 60)
        print(f"  Clips: {', '.join(c.name for c in clips)}")
        print(f"  Output: {output_path}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="terrasat_conv_"))
    try:
        print(f"\n[1/5] Generando {len(guion)} segmentos de voz...")
        segments = await generate_voice_segments(guion, tmp_dir)

        print(f"\n[2/5] Ensamblando audio con interrupciones y solapamientos...")
        full_audio = concat_audio_segments(segments, tmp_dir)
        audio_dur = get_duration(full_audio)
        print(f"      Audio final: {audio_dur:.1f}s")

        print(f"\n[3/5] Procesando video con branding + fades...")
        build_video(full_audio, clips, output_path, tmp_dir)

        print(f"\n[5/5] ¡Listo!")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
