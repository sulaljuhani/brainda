'use client';

interface Citation {
  type: string;
  id: string;
  title: string;
  chunk_index?: number;
  location?: string;
  excerpt: string;
}

interface Props {
  citations: Citation[];
}

export default function CitationRenderer({ citations }: Props) {
  if (!citations || !citations.length) return null;

  return (
    <div className="mt-4 border-t pt-4">
      <h4 className="text-sm font-semibold mb-2">Sources</h4>
      <div className="space-y-2">
        {citations.map((citation, idx) => (
          <div key={`${citation.id}-${idx}`} className="text-sm bg-gray-50 p-3 rounded">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <span className="font-medium">
                  [{idx + 1}] {citation.title}
                </span>
                {citation.location && (
                  <span className="text-gray-500 ml-2">{citation.location}</span>
                )}
              </div>
              <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                {citation.type}
              </span>
            </div>
            <p className="text-gray-600 mt-1 text-xs italic">"{citation.excerpt}"</p>
          </div>
        ))}
      </div>
    </div>
  );
}
