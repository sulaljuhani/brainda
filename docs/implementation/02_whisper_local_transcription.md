# Local Whisper Transcription - Implementation Plan

## Overview
Enable speech-to-text transcription using locally-hosted OpenAI Whisper model. Supports real-time voice input in chat, voice memos, and audio file transcription.

## Use Cases
- Hold microphone button → Speak → Text appears in chat input
- Upload audio file → Auto-transcribe → Create note/task from transcript
- Voice memo → Save as note with transcription
- Meeting recording → Transcribe → Create meeting summary

---

## Phase 1: Dependencies & Docker Setup (1 hour)

### Update: `requirements.txt`

```txt
# Whisper and audio processing
openai-whisper==20231117
ffmpeg-python==0.2.0
soundfile==0.12.1
librosa==0.10.1

# Optional: faster-whisper (10x faster with same quality)
# faster-whisper==0.10.0
```

### Update: `Dockerfile.dev`

```dockerfile
# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
```

### Update: `docker-compose.dev.yml`

Add environment variables for Whisper configuration:

```yaml
services:
  worker:
    environment:
      # Whisper model size: tiny, base, small, medium, large
      WHISPER_MODEL_SIZE: base

      # Model cache directory (persistent volume)
      WHISPER_MODEL_CACHE: /app/.cache/whisper

      # Device: cpu or cuda
      WHISPER_DEVICE: cpu

      # Language (auto-detect if not specified)
      WHISPER_DEFAULT_LANGUAGE: en

    volumes:
      # Persist downloaded models
      - ./cache/whisper:/app/.cache/whisper
```

### Whisper Model Comparison

| Model | Size | Speed (CPU) | Speed (GPU) | Accuracy | VRAM | Use Case |
|-------|------|-------------|-------------|----------|------|----------|
| `tiny` | 75 MB | ~32x realtime | ~10x realtime | 65% WER | 1 GB | Quick notes, low-end hardware |
| `base` | 142 MB | ~16x realtime | ~7x realtime | 50% WER | 1 GB | **Recommended for CPU** |
| `small` | 466 MB | ~6x realtime | ~4x realtime | 35% WER | 2 GB | **Recommended for GPU** |
| `medium` | 1.5 GB | ~2x realtime | ~2x realtime | 25% WER | 5 GB | High accuracy needs |
| `large` | 2.9 GB | ~1x realtime | ~1x realtime | 20% WER | 10 GB | Production, multilingual |

**Recommendation**:
- **CPU-only**: Use `base` (good balance)
- **GPU available**: Use `small` (10x faster, better accuracy)
- **Production**: Use `faster-whisper` + `small` model

---

## Phase 2: Worker - Whisper Model Loading (1 hour)

### Update: `app/worker/tasks.py`

Add Whisper model initialization:

```python
import whisper
import os
from pathlib import Path
import structlog

logger = structlog.get_logger()

# Global model instance (loaded once per worker)
WHISPER_MODEL = None
WHISPER_MODEL_LOCK = threading.Lock()

def get_whisper_model():
    """Load Whisper model (singleton per worker process)."""
    global WHISPER_MODEL

    if WHISPER_MODEL is None:
        with WHISPER_MODEL_LOCK:
            # Double-check after acquiring lock
            if WHISPER_MODEL is None:
                model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
                device = os.getenv("WHISPER_DEVICE", "cpu")
                cache_dir = os.getenv("WHISPER_MODEL_CACHE", "/app/.cache/whisper")

                logger.info(
                    "whisper_model_loading",
                    model_size=model_size,
                    device=device,
                    cache_dir=cache_dir,
                )

                # Create cache directory
                Path(cache_dir).mkdir(parents=True, exist_ok=True)

                # Download and load model (cached after first download)
                WHISPER_MODEL = whisper.load_model(
                    model_size,
                    device=device,
                    download_root=cache_dir,
                )

                logger.info("whisper_model_loaded", model_size=model_size)

    return WHISPER_MODEL


@celery_app.task(bind=True, max_retries=3, soft_time_limit=180, time_limit=240)
def transcribe_audio_task(self, audio_file_path: str, language: str = None) -> dict:
    """
    Transcribe audio file using local Whisper model.

    Args:
        audio_file_path: Path to audio file (mp3, wav, m4a, webm, etc.)
        language: ISO 639-1 language code (None for auto-detect)

    Returns:
        {
            "text": str,
            "language": str,
            "duration": float,
            "segments": list,
        }
    """
    try:
        model = get_whisper_model()

        logger.info("transcribe_audio_start", file_path=audio_file_path, language=language)

        # Transcribe
        result = model.transcribe(
            audio_file_path,
            language=language or os.getenv("WHISPER_DEFAULT_LANGUAGE"),
            fp16=False,  # Set to True if using GPU with FP16 support
            verbose=False,

            # Optional: improve accuracy with these settings
            temperature=0.0,  # Deterministic output
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.6,

            # Optional: enable word-level timestamps
            word_timestamps=True,
        )

        # Extract key information
        transcript = {
            "text": result["text"].strip(),
            "language": result["language"],
            "duration": result.get("duration", 0),
            "segments": [
                {
                    "id": seg["id"],
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"].strip(),
                }
                for seg in result.get("segments", [])
            ],
        }

        logger.info(
            "transcribe_audio_complete",
            file_path=audio_file_path,
            language=transcript["language"],
            duration=transcript["duration"],
            text_preview=transcript["text"][:100],
        )

        # Cleanup temp file
        if os.path.exists(audio_file_path) and "/tmp/" in audio_file_path:
            os.remove(audio_file_path)
            logger.debug("transcribe_audio_cleanup", file_path=audio_file_path)

        return transcript

    except Exception as exc:
        logger.error("transcribe_audio_failed", file_path=audio_file_path, error=str(exc))

        # Cleanup on error
        if os.path.exists(audio_file_path) and "/tmp/" in audio_file_path:
            os.remove(audio_file_path)

        # Retry on transient errors
        raise self.retry(exc=exc, countdown=10)


# Alternative: faster-whisper implementation (10x faster)
"""
from faster_whisper import WhisperModel

FASTER_WHISPER_MODEL = None

def get_faster_whisper_model():
    global FASTER_WHISPER_MODEL

    if FASTER_WHISPER_MODEL is None:
        model_size = os.getenv("WHISPER_MODEL_SIZE", "base")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = "int8" if device == "cpu" else "float16"

        FASTER_WHISPER_MODEL = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            download_root=os.getenv("WHISPER_MODEL_CACHE", "/app/.cache/whisper"),
        )

    return FASTER_WHISPER_MODEL

@celery_app.task(bind=True)
def transcribe_audio_faster(self, audio_file_path: str, language: str = None):
    model = get_faster_whisper_model()

    segments, info = model.transcribe(
        audio_file_path,
        language=language,
        beam_size=5,
        word_timestamps=True,
    )

    # Convert segments generator to list
    segments_list = []
    full_text = []

    for segment in segments:
        segments_list.append({
            "id": segment.id,
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
        })
        full_text.append(segment.text)

    return {
        "text": " ".join(full_text).strip(),
        "language": info.language,
        "duration": info.duration,
        "segments": segments_list,
    }
"""
```

---

## Phase 3: Backend - Transcription API (1 hour)

### Create: `app/api/routers/transcribe.py` (NEW)

```python
"""Speech-to-text transcription endpoints."""
import os
import time
import uuid
from typing import Optional

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, Form
from pydantic import BaseModel
import structlog

from api.dependencies import get_current_user, get_db

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/transcribe", tags=["transcribe"])


class TranscriptionResponse(BaseModel):
    """Transcription result."""
    text: str
    language: str
    duration: float
    segments: list
    status: str = "completed"


class TranscriptionTask(BaseModel):
    """Async transcription task."""
    task_id: str
    status: str  # pending, processing, completed, failed
    text: Optional[str] = None
    error: Optional[str] = None


@router.post("", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    wait: bool = Form(True),  # Wait for result or return task_id
    user_id: uuid.UUID = Depends(get_current_user),
):
    """
    Transcribe audio file using local Whisper model.

    Supported formats: mp3, wav, m4a, webm, ogg, flac
    Max file size: 25MB
    Max duration: 10 minutes
    """

    # Validate content type
    allowed_types = [
        "audio/mpeg", "audio/mp3",
        "audio/wav", "audio/wave",
        "audio/m4a", "audio/mp4",
        "audio/webm",
        "audio/ogg",
        "audio/flac",
    ]

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {file.content_type}. "
                   f"Supported: mp3, wav, m4a, webm, ogg, flac"
        )

    # Read file content
    content = await file.read()

    # Validate file size (max 25MB)
    max_size = 25 * 1024 * 1024  # 25MB
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(content)} bytes. Max: {max_size} bytes (25MB)"
        )

    # Save to temporary file
    ext = os.path.splitext(file.filename)[1] or ".webm"
    temp_filename = f"audio_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}{ext}"
    temp_path = f"/tmp/{temp_filename}"

    with open(temp_path, "wb") as f:
        f.write(content)

    logger.info(
        "transcribe_audio_request",
        user_id=str(user_id),
        filename=file.filename,
        size_bytes=len(content),
        language=language,
    )

    # Queue transcription task
    from worker.tasks import transcribe_audio_task

    task = transcribe_audio_task.delay(temp_path, language)

    # If wait=False, return task ID immediately
    if not wait:
        return TranscriptionTask(
            task_id=task.id,
            status="processing",
        )

    # Wait for result (with timeout)
    try:
        result = task.get(timeout=120)  # 2 minute timeout

        return TranscriptionResponse(
            text=result["text"],
            language=result["language"],
            duration=result["duration"],
            segments=result["segments"],
            status="completed",
        )

    except Exception as exc:
        logger.error("transcribe_audio_timeout", task_id=task.id, error=str(exc))

        # Return task ID for polling
        raise HTTPException(
            status_code=202,
            detail={
                "message": "Transcription is taking longer than expected. Use the task_id to check status.",
                "task_id": task.id,
            }
        )


@router.get("/tasks/{task_id}", response_model=TranscriptionTask)
async def get_transcription_task(
    task_id: str,
    user_id: uuid.UUID = Depends(get_current_user),
):
    """Check status of async transcription task."""
    from celery.result import AsyncResult

    task = AsyncResult(task_id)

    if task.ready():
        if task.successful():
            result = task.result
            return TranscriptionTask(
                task_id=task_id,
                status="completed",
                text=result["text"],
            )
        else:
            return TranscriptionTask(
                task_id=task_id,
                status="failed",
                error=str(task.info),
            )

    return TranscriptionTask(
        task_id=task_id,
        status="processing",
    )
```

### Update: `app/api/main.py`

Register the transcribe router:

```python
from api.routers import transcribe

app.include_router(transcribe.router)
```

---

## Phase 4: Frontend - Voice Recorder Component (2-3 hours)

### Create: `app/web/src/components/chat/VoiceRecorder.tsx` (NEW)

```typescript
import { useState, useRef, useEffect } from 'react';
import { Mic, Square, Loader } from 'lucide-react';
import './VoiceRecorder.css';

interface VoiceRecorderProps {
  onTranscription: (text: string) => void;
  onError?: (error: string) => void;
}

export function VoiceRecorder({ onTranscription, onError }: VoiceRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => {
    // Cleanup on unmount
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
      }
    };
  }, []);

  const startRecording = async () => {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100,
        },
      });

      streamRef.current = stream;

      // Determine best supported MIME type
      const mimeTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/ogg;codecs=opus',
        'audio/mp4',
      ];

      const supportedMimeType = mimeTypes.find(type => MediaRecorder.isTypeSupported(type));

      if (!supportedMimeType) {
        throw new Error('No supported audio format found');
      }

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: supportedMimeType,
      });

      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: supportedMimeType });
        await transcribeAudio(audioBlob);

        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordingTime(0);
      setErrorMessage(null);

      // Start timer
      timerRef.current = window.setInterval(() => {
        setRecordingTime(prev => prev + 1);
      }, 1000);

    } catch (err) {
      console.error('Microphone access error:', err);
      const message = err instanceof Error ? err.message : 'Microphone access denied';
      setErrorMessage(message);
      onError?.(message);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);

      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  };

  const transcribeAudio = async (audioBlob: Blob) => {
    setIsProcessing(true);

    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.webm');
    formData.append('wait', 'true');

    try {
      const token = localStorage.getItem('token');

      const response = await fetch('/api/v1/transcribe', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail?.message || 'Transcription failed');
      }

      const data = await response.json();

      if (data.text) {
        onTranscription(data.text);
      } else {
        throw new Error('No transcription returned');
      }

    } catch (err) {
      console.error('Transcription error:', err);
      const message = err instanceof Error ? err.message : 'Transcription failed';
      setErrorMessage(message);
      onError?.(message);
    } finally {
      setIsProcessing(false);
      setRecordingTime(0);
    }
  };

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="voice-recorder">
      <button
        onMouseDown={startRecording}
        onMouseUp={stopRecording}
        onMouseLeave={stopRecording}
        onTouchStart={startRecording}
        onTouchEnd={stopRecording}
        disabled={isProcessing}
        className={`voice-recorder__button ${isRecording ? 'recording' : ''} ${isProcessing ? 'processing' : ''}`}
        title={isRecording ? 'Release to stop' : 'Hold to record'}
      >
        {isProcessing ? (
          <Loader size={20} className="voice-recorder__spinner" />
        ) : isRecording ? (
          <Square size={20} />
        ) : (
          <Mic size={20} />
        )}
      </button>

      {isRecording && (
        <div className="voice-recorder__indicator">
          <span className="voice-recorder__dot"></span>
          <span className="voice-recorder__time">{formatTime(recordingTime)}</span>
        </div>
      )}

      {isProcessing && (
        <div className="voice-recorder__status">Transcribing...</div>
      )}

      {errorMessage && (
        <div className="voice-recorder__error">{errorMessage}</div>
      )}
    </div>
  );
}
```

### Create: `app/web/src/components/chat/VoiceRecorder.css` (NEW)

```css
.voice-recorder {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
}

.voice-recorder__button {
  padding: 8px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  border-radius: 4px;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.voice-recorder__button:hover:not(:disabled) {
  background: var(--background-hover);
  color: var(--text-primary);
}

.voice-recorder__button.recording {
  color: var(--error-color);
  background: var(--error-background);
  animation: pulse 1.5s ease-in-out infinite;
}

.voice-recorder__button.processing {
  color: var(--primary-color);
  cursor: not-allowed;
}

.voice-recorder__button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.voice-recorder__spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.voice-recorder__indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  background: var(--error-background);
  border-radius: 12px;
  font-size: 14px;
  color: var(--error-color);
  font-weight: 500;
}

.voice-recorder__dot {
  width: 8px;
  height: 8px;
  background: var(--error-color);
  border-radius: 50%;
  animation: blink 1s ease-in-out infinite;
}

@keyframes blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}

.voice-recorder__time {
  font-variant-numeric: tabular-nums;
  min-width: 40px;
}

.voice-recorder__status {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 4px 8px;
  background: var(--background-secondary);
  border-radius: 4px;
}

.voice-recorder__error {
  position: absolute;
  bottom: -30px;
  left: 0;
  font-size: 12px;
  color: var(--error-color);
  background: var(--error-background);
  padding: 4px 8px;
  border-radius: 4px;
  white-space: nowrap;
}
```

---

## Phase 5: Integration with ChatInput (30 mins)

### Update: `app/web/src/components/chat/ChatInput.tsx`

```typescript
import { VoiceRecorder } from './VoiceRecorder';

export function ChatInput({ onSendMessage, disabled }: ChatInputProps) {
  const [message, setMessage] = useState('');

  const handleVoiceTranscription = (text: string) => {
    // Append transcription to current message
    setMessage(prev => prev ? `${prev} ${text}` : text);

    // Focus textarea
    textareaRef.current?.focus();
  };

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      <div className="chat-input__wrapper">
        <textarea ... />

        {/* Voice recorder */}
        <VoiceRecorder
          onTranscription={handleVoiceTranscription}
          onError={(err) => console.error('Voice recording error:', err)}
        />

        {/* File attach button */}
        <button type="button" onClick={...}>
          <Paperclip size={20} />
        </button>

        <button type="submit">
          <Send size={20} />
        </button>
      </div>
    </form>
  );
}
```

---

## Phase 6: Advanced Features (Optional)

### 6.1 Voice Memos (Save as Notes)

Create dedicated voice memo page:

```typescript
// app/web/src/pages/VoiceMemosPage.tsx
export function VoiceMemosPage() {
  const [isRecording, setIsRecording] = useState(false);
  const [memos, setMemos] = useState([]);

  const handleRecordingComplete = async (audioBlob: Blob) => {
    // 1. Upload audio file
    // 2. Transcribe
    // 3. Create note with transcript + audio attachment
    // 4. Refresh memos list
  };

  return (
    <div>
      <h1>Voice Memos</h1>
      <VoiceRecorder onComplete={handleRecordingComplete} />
      <MemosList memos={memos} />
    </div>
  );
}
```

### 6.2 Real-time Streaming Transcription

For longer recordings, show partial transcriptions:

```python
# Backend: Stream transcription segments as they're ready
@router.post("/transcribe/stream")
async def transcribe_audio_stream(file: UploadFile):
    # Use faster-whisper or word-level timestamps
    # Yield partial results as SSE (Server-Sent Events)
    pass
```

### 6.3 Speaker Diarization

Identify different speakers in conversation:

```bash
# Add pyannote-audio for speaker diarization
pip install pyannote-audio
```

### 6.4 Automatic Punctuation & Formatting

Use recasepunc for better formatting:

```bash
pip install recasepunc
```

---

## Testing Checklist

- [ ] Click microphone button → Recording starts
- [ ] Hold for 5 seconds → Release → Transcription appears
- [ ] Upload MP3 file → Transcription returned
- [ ] Upload 2-minute audio → Completes within 30 seconds
- [ ] Speak in different language → Auto-detected correctly
- [ ] Network interruption during transcription → Retries gracefully
- [ ] Concurrent transcriptions → All complete successfully
- [ ] Model loads only once per worker → Fast subsequent requests
- [ ] Worker restart → Model reloads automatically

---

## Performance Optimization

### CPU Performance
```yaml
# docker-compose.dev.yml
worker:
  environment:
    WHISPER_MODEL_SIZE: base  # Fast on CPU

  # Dedicate CPU cores to worker
  cpus: 4
```

### GPU Acceleration (NVIDIA)
```yaml
worker:
  environment:
    WHISPER_MODEL_SIZE: small
    WHISPER_DEVICE: cuda

  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### Benchmarks (base model, 1-minute audio)
- **CPU (4 cores)**: ~7 seconds
- **GPU (T4)**: ~1 second
- **faster-whisper (CPU)**: ~2 seconds
- **faster-whisper (GPU)**: ~0.5 seconds

---

## Error Handling

### Common Errors

1. **No microphone permission**
   - Show browser-specific instructions
   - Provide settings link

2. **Audio too quiet**
   - Check input gain in browser
   - Add noise gate threshold

3. **Transcription timeout**
   - Return task_id for polling
   - Show progress indicator

4. **Model download failure**
   - Pre-download models during Docker build
   - Use local model cache

5. **Out of memory**
   - Use smaller model (tiny/base)
   - Reduce worker concurrency

---

## Monitoring & Metrics

Add Prometheus metrics:

```python
from prometheus_client import Histogram, Counter

transcription_duration = Histogram(
    "transcription_duration_seconds",
    "Time taken to transcribe audio",
    ["model_size", "audio_duration_bucket"],
)

transcription_requests = Counter(
    "transcription_requests_total",
    "Total transcription requests",
    ["status", "language"],
)
```

---

## Estimated Total Time: 6-8 hours

- Phase 1 (Dependencies): 1 hour
- Phase 2 (Model loading): 1 hour
- Phase 3 (API): 1 hour
- Phase 4 (Frontend): 2-3 hours
- Phase 5 (Integration): 30 mins
- Testing & polish: 1 hour
