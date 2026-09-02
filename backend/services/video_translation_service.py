import os
import zipfile
import torch
import whisper
from gtts import gTTS
from moviepy.editor import VideoFileClip, AudioFileClip

# Supported languages dictionary (extend as needed)
TARGET_LANGUAGES = {
    "hi": "Hindi",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "bn": "Bengali"
}

def process_video_translation(video_path, output_dir):
    """
    Extracts audio, transcribes, translates to multiple languages, 
    generates dubbed video files, and packs them into a ZIP archive.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Extract audio from uploaded video
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    audio_path = os.path.join(output_dir, f"{base_name}.mp3")
    
    video_clip = VideoFileClip(video_path)
    video_clip.audio.write_audiofile(audio_path)
    
    # 2. Transcribe audio using OpenAI Whisper
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
    transcript_text = result["text"]
    
    generated_files = []
    
    # Save original transcript
    transcript_file = os.path.join(output_dir, f"{base_name}_transcript.txt")
    with open(transcript_file, "w", encoding="utf-8") as f:
        f.write(transcript_text)
    generated_files.append(transcript_file)

    # 3. Translate and dub for each target language
    from transformers import pipeline
    
    for lang_code, lang_name in TARGET_LANGUAGES.items():
        try:
            # Translation pipeline (using HuggingFace transformers)
            translator = pipeline("translation", model=f"Helsinki-NLP/opus-mt-en-{lang_code}")
            translated_text = translator(transcript_text, max_length=512)[0]['translation_text']
            
            # Save translated text file
            trans_text_path = os.path.join(output_dir, f"{base_name}_{lang_code}.txt")
            with open(trans_text_path, "w", encoding="utf-8") as f:
                f.write(translated_text)
            generated_files.append(trans_text_path)
            
            # Text to Speech synthesis
            tts = gTTS(text=translated_text, lang=lang_code, slow=False)
            lang_audio_path = os.path.join(output_dir, f"{base_name}_{lang_code}.mp3")
            tts.save(lang_audio_path)
            
            # Merge translated audio back into the video
            new_audio = AudioFileClip(lang_audio_path)
            translated_video_clip = video_clip.set_audio(new_audio)
            
            output_video_path = os.path.join(output_dir, f"{base_name}_{lang_code}.mp4")
            translated_video_clip.write_videofile(output_video_path, codec="libx264", audio_codec="aac")
            generated_files.append(output_video_path)
            
        except Exception as e:
            print(f"Failed processing for language {lang_name}: {str(e)}")

    # Close clips to release resources
    video_clip.close()

    # 4. Pack all generated files into a ZIP archive
    zip_path = os.path.join(output_dir, f"{base_name}_translated_files.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in generated_files:
            zipf.write(file, os.path.basename(file))
            
    return zip_path
