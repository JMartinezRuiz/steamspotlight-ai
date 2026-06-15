from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, ImageClip
from PIL import Image, ImageFilter
import numpy as np
import os

def apply_blur_and_add_audio(input_video_path, input_audio_path, output_video_path, blur_radius=10):
    """
    Aplica un efecto de desenfoque a un video, mutea su audio, agrega un nuevo audio
    y superpone un logo rotatorio en el centro del video.

    :param input_video_path: Ruta al video de entrada.
    :param input_audio_path: Ruta al archivo de audio a agregar.
    :param output_video_path: Ruta donde se guardará el video editado.
    :param blur_radius: Radio del desenfoque (mayor valor, más desenfoque).
    """
    print(f"Abriendo video de entrada: {input_video_path}")
    try:
        clip = VideoFileClip(input_video_path)
    except Exception as e:
        print(f"Error al abrir el video: {e}")
        return

    print("Bajando el volumen al 0% (muteando)")
    clip = clip.volumex(0)  # Mutea el audio

    print(f"Aplicando efecto de desenfoque con radio: {blur_radius}")
    try:
        # Definir una función que aplica desenfoque a cada cuadro
        def blur_frame(frame):
            # Convertir el cuadro a una imagen PIL
            pil_image = Image.fromarray(frame)
            # Aplicar desenfoque Gaussian Blur
            blurred_image = pil_image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            # Convertir la imagen de vuelta a un arreglo numpy
            return np.array(blurred_image)

        # Aplicar la función de desenfoque a cada cuadro del video
        clip = clip.fl_image(blur_frame)
        print("Efecto de desenfoque aplicado.")
    except Exception as e:
        print(f"Error al aplicar el efecto de desenfoque: {e}")
        clip.close()
        return

    # Agregar el audio `description.mp3`
    print(f"Agregando audio: {input_audio_path}")
    if not os.path.exists(input_audio_path):
        print(f"El archivo de audio no existe: {input_audio_path}")
        clip.close()
        return
    try:
        audio_clip = AudioFileClip(input_audio_path)
        # Asegurar que el audio y el video tengan la misma duración
        audio_duration = audio_clip.duration
        video_duration = clip.duration
        if audio_duration < video_duration:
            clip = clip.subclip(0, audio_duration)
            video_duration = audio_duration
            print(f"Video recortado a la duración del audio: {video_duration} segundos")
        elif audio_duration > video_duration:
            audio_clip = audio_clip.subclip(0, video_duration)
            print(f"Audio recortado a la duración del video: {video_duration} segundos")
        clip = clip.set_audio(audio_clip)
        print("Audio agregado al video.")
    except Exception as e:
        print(f"Error al agregar el audio: {e}")
        clip.close()
        audio_clip.close()
        return

    # Ruta al logo
    logo_path = os.path.join(os.path.dirname(input_video_path), 'logo.png')
    if not os.path.exists(logo_path):
        print(f"El archivo de logo no existe: {logo_path}")
        clip.close()
        audio_clip.close()
        return

    print("Creando logo rotatorio")
    try:
        # Crear un ImageClip del logo
        logo = ImageClip(logo_path)
        # Redimensionar el logo si es necesario (opcional)
        logo_width = int(clip.w * 0.2)  # Ajusta el tamaño del logo al 20% del ancho del video
        logo = logo.resize(width=logo_width)
        # Establecer la duración del logo igual a la del video
        logo = logo.set_duration(clip.duration)
        # Posicionar el logo en el centro
        logo = logo.set_position('center')
        # Aplicar rotación continua al logo
        rotation_speed = 100  # Grados por segundo (ajusta este valor según prefieras)
        logo = logo.rotate(lambda t: rotation_speed * t, expand=False)
    except Exception as e:
        print(f"Error al crear el logo rotatorio: {e}")
        clip.close()
        audio_clip.close()
        return

    # Combinar el video con el logo rotatorio
    final_clip = CompositeVideoClip([clip, logo])

    print(f"Exportando video editado a: {output_video_path}")
    try:
        final_clip.write_videofile(
            output_video_path,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile="temp-audio.m4a",
            remove_temp=True,
            fps=24
        )
    except Exception as e:
        print(f"Error al exportar el video: {e}")
    finally:
        clip.close()
        audio_clip.close()
        final_clip.close()

    print("Video editado generado con éxito.")

if __name__ == "__main__":
    # Definir rutas
    current_dir = os.getcwd()
    video_folder = os.path.join(current_dir, 'A Quiet Place The Road Ahead')
    input_video = os.path.join(video_folder, 'media2.mp4')
    input_audio = os.path.join(video_folder, 'description.mp3')
    output_video = os.path.join(video_folder, 'blur_testing.mp4')

    # Verificar que el video y el audio de entrada existen
    if not os.path.exists(input_video):
        print(f"El video de entrada no existe: {input_video}")
    elif not os.path.exists(input_audio):
        print(f"El archivo de audio no existe: {input_audio}")
    else:
        # Aplicar efectos y generar el video editado
        apply_blur_and_add_audio(input_video, input_audio, output_video, blur_radius=20)
