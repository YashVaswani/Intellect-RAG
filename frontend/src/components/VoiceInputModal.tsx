"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Mic, MicOff, Upload, X, Send, Loader2 } from "lucide-react";

interface VoiceInputModalProps {
  onClose: () => void;
  onTranscript: (text: string) => void;
}

export default function VoiceInputModal({ onClose, onTranscript }: VoiceInputModalProps) {
  const [phase, setPhase] = useState<"idle" | "recording" | "processing" | "done">("idle");
  const [seconds, setSeconds] = useState(0);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState("");
  const [bars, setBars] = useState<number[]>(Array(24).fill(4));

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Animate bars from analyser or idle wave
  const animateBars = useCallback(() => {
    if (analyserRef.current) {
      const data = new Uint8Array(analyserRef.current.frequencyBinCount);
      analyserRef.current.getByteFrequencyData(data);
      const step = Math.floor(data.length / 24);
      setBars(Array.from({ length: 24 }, (_, i) => Math.max(4, Math.round((data[i * step] / 255) * 60))));
    } else {
      setBars(prev => prev.map((_, i) => 4 + Math.round(Math.abs(Math.sin(Date.now() / 600 + i * 0.4)) * 10)));
    }
    animFrameRef.current = requestAnimationFrame(animateBars);
  }, []);

  useEffect(() => {
    animFrameRef.current = requestAnimationFrame(animateBars);
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [animateBars]);

  const startRecording = async () => {
    setError("");
    setTranscript("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      const ctx = new AudioContext();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      source.connect(analyser);
      analyserRef.current = analyser;

      const mimeType = MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        analyserRef.current = null;
        const blob = new Blob(chunksRef.current, { type: mimeType });
        await transcribeBlob(blob, mimeType === "audio/webm" ? "recording.webm" : "recording.mp4");
      };

      recorder.start(100);
      mediaRecorderRef.current = recorder;
      setPhase("recording");
      setSeconds(0);
      timerRef.current = setInterval(() => setSeconds(s => s + 1), 1000);
    } catch (err: unknown) {
      setError("Microphone access denied. Please allow microphone permissions and try again.");
      console.error(err);
    }
  };

  const stopRecording = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    setPhase("processing");
  };

  const transcribeBlob = async (blob: Blob, filename: string) => {
    setPhase("processing");
    const formData = new FormData();
    formData.append("file", blob, filename);
    try {
      const res = await fetch("/api/documents/audio-transcribe", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (data.success && data.transcript) {
        setTranscript(data.transcript);
        setPhase("done");
      } else {
        setError(data.error || "Transcription failed. Please try again.");
        setPhase("idle");
      }
    } catch {
      setError("Network error during transcription.");
      setPhase("idle");
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    await transcribeBlob(file, file.name);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleSend = () => {
    if (transcript.trim()) {
      onTranscript(transcript.trim());
      onClose();
    }
  };

  const formatTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center pb-6 px-4"
      style={{ background: "rgba(0,0,0,0.55)", backdropFilter: "blur(4px)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-border bg-card shadow-2xl overflow-hidden"
        style={{ animation: "slideUp 0.25s ease" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-3">
          <span className="font-semibold text-foreground text-base">Voice Input</span>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-secondary text-muted-foreground hover:text-foreground transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Waveform */}
        <div className="flex items-center justify-center gap-[3px] h-20 px-6">
          {bars.map((h, i) => (
            <div
              key={i}
              className="rounded-full transition-all duration-75"
              style={{
                width: 4,
                height: h,
                background: phase === "recording"
                  ? `hsl(${220 + i * 2}, 80%, 60%)`
                  : phase === "processing"
                  ? "hsl(45, 90%, 60%)"
                  : "hsl(220, 15%, 40%)",
                opacity: phase === "idle" ? 0.4 : 1,
              }}
            />
          ))}
        </div>

        {/* Status text */}
        <div className="text-center pb-2 min-h-[40px] px-6">
          {phase === "idle" && (
            <p className="text-sm text-muted-foreground">Press the mic to start recording</p>
          )}
          {phase === "recording" && (
            <p className="text-sm font-mono text-primary animate-pulse">
              🔴 Recording — {formatTime(seconds)}
            </p>
          )}
          {phase === "processing" && (
            <p className="text-sm text-yellow-500 flex items-center justify-center gap-2">
              <Loader2 size={14} className="animate-spin" /> Transcribing…
            </p>
          )}
          {phase === "done" && transcript && (
            <p className="text-xs text-muted-foreground italic line-clamp-2">"{transcript}"</p>
          )}
          {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between px-5 pb-5 pt-3 gap-3">
          {/* Upload file */}
          <label
            className="flex items-center gap-2 px-3 py-2 rounded-xl border border-border text-sm text-muted-foreground hover:text-foreground hover:bg-secondary cursor-pointer transition-colors"
            title="Upload an audio file instead"
          >
            <Upload size={15} />
            <span>Upload file</span>
            <input
              ref={fileInputRef}
              type="file"
              accept=".mp3,.wav,.m4a,.ogg,.flac,.webm"
              className="hidden"
              onChange={handleFileUpload}
            />
          </label>

          {/* Mic / Stop */}
          <button
            onClick={phase === "recording" ? stopRecording : startRecording}
            disabled={phase === "processing"}
            className={`flex items-center justify-center w-14 h-14 rounded-full transition-all shadow-lg ${
              phase === "recording"
                ? "bg-red-500 hover:bg-red-600 text-white scale-110"
                : phase === "processing"
                ? "bg-secondary text-muted-foreground cursor-not-allowed"
                : "bg-primary hover:bg-primary/90 text-primary-foreground"
            }`}
          >
            {phase === "processing" ? (
              <Loader2 size={22} className="animate-spin" />
            ) : phase === "recording" ? (
              <MicOff size={22} />
            ) : (
              <Mic size={22} />
            )}
          </button>

          {/* Send */}
          <button
            onClick={handleSend}
            disabled={!transcript.trim() || phase !== "done"}
            className={`flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
              transcript.trim() && phase === "done"
                ? "bg-primary text-primary-foreground hover:bg-primary/90"
                : "bg-secondary text-muted-foreground cursor-not-allowed opacity-50"
            }`}
          >
            <Send size={15} />
            Send
          </button>
        </div>
      </div>

      <style>{`
        @keyframes slideUp {
          from { transform: translateY(40px); opacity: 0; }
          to   { transform: translateY(0);   opacity: 1; }
        }
      `}</style>
    </div>
  );
}
