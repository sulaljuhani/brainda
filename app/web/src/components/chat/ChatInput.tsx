import { useState, useRef, useEffect, FormEvent, KeyboardEvent, ChangeEvent } from 'react';
import { Send, Paperclip, X } from 'lucide-react';
import './ChatInput.css';

interface AttachmentPreview {
  file: File;
  id: string;
  preview?: string;
  type: 'image' | 'document' | 'audio' | 'other';
}

interface ChatInputProps {
  onSendMessage: (message: string, files?: File[]) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({ onSendMessage, disabled = false, placeholder = 'Ask me anything...' }: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [attachments, setAttachments] = useState<AttachmentPreview[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [message]);

  const detectFileType = (file: File): AttachmentPreview['type'] => {
    if (file.type.startsWith('image/')) return 'image';
    if (file.type.startsWith('audio/')) return 'audio';
    if (file.type === 'application/pdf') return 'document';
    return 'other';
  };

  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const newAttachments: AttachmentPreview[] = [];

    Array.from(files).forEach((file) => {
      const type = detectFileType(file);
      const id = Math.random().toString(36).substring(7);

      // Create preview for images
      if (type === 'image') {
        const reader = new FileReader();
        reader.onload = (event) => {
          setAttachments((prev) =>
            prev.map((att) =>
              att.id === id ? { ...att, preview: event.target?.result as string } : att
            )
          );
        };
        reader.readAsDataURL(file);
      }

      newAttachments.push({ file, id, type });
    });

    setAttachments((prev) => [...prev, ...newAttachments]);

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((att) => att.id !== id));
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if ((message.trim() || attachments.length > 0) && !disabled) {
      const files = attachments.map((att) => att.file);
      onSendMessage(message.trim(), files);
      setMessage('');
      setAttachments([]);
      // Reset textarea height
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Send on Enter, newline on Shift+Enter
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value);
  };

  return (
    <form className="chat-input" onSubmit={handleSubmit}>
      {/* File previews */}
      {attachments.length > 0 && (
        <div className="chat-input__attachments">
          {attachments.map((att) => (
            <div key={att.id} className="chat-input__attachment">
              {att.type === 'image' && att.preview ? (
                <img src={att.preview} alt={att.file.name} className="attachment-preview" />
              ) : (
                <div className="attachment-icon">
                  {att.type === 'audio' ? '🎵' : '📄'}
                </div>
              )}
              <div className="attachment-info">
                <div className="attachment-name">{att.file.name}</div>
                <div className="attachment-size">
                  {(att.file.size / 1024).toFixed(1)} KB
                </div>
              </div>
              <button
                type="button"
                onClick={() => removeAttachment(att.id)}
                className="attachment-remove"
                aria-label="Remove attachment"
              >
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="chat-input__wrapper">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={attachments.length > 0 ? "Add a message..." : placeholder}
          disabled={disabled}
          className="chat-input__textarea"
          rows={1}
          maxLength={10000}
        />

        {/* File upload button */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*,application/pdf,audio/*,.txt,.md,.doc,.docx"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
          aria-label="File input"
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="chat-input__attach-button"
          disabled={disabled}
          title="Attach files"
          aria-label="Attach files"
        >
          <Paperclip size={20} />
        </button>

        <button
          type="submit"
          disabled={disabled || (!message.trim() && attachments.length === 0)}
          className="chat-input__send-button"
          aria-label="Send message"
        >
          <Send size={20} />
        </button>
      </div>
      {message.length > 9000 && (
        <div className="chat-input__counter">
          {message.length} / 10000
        </div>
      )}
    </form>
  );
}
