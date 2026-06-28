import ReactMarkdown from "react-markdown";

const MARKDOWN_PATTERN = /^#|^\*\*|^-\s/m;

interface AnalysisContentProps {
  text: string;
}

export function AnalysisContent({ text }: AnalysisContentProps) {
  if (!text) return null;

  if (MARKDOWN_PATTERN.test(text)) {
    return (
      <div className="atlas-prose atlas-tile-body">
        <ReactMarkdown>{text}</ReactMarkdown>
      </div>
    );
  }

  const paragraphs = text.split(/\n\n+/).filter((part) => part.trim());
  if (paragraphs.length <= 1) {
    return <p className="atlas-tile-body">{text}</p>;
  }

  return (
    <div className="atlas-tile-body">
      {paragraphs.map((paragraph, index) => (
        <p key={index} className="mb-3 last:mb-0">
          {paragraph.trim()}
        </p>
      ))}
    </div>
  );
}
