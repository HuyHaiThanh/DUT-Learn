import { Link } from 'react-router-dom';

export interface ContinueReadingProps {
  to: string;
  courseName: string;
  title: string;
  pageLabel: string;
  pageCount: number;
  lastOpenedLabel: string;
  questionCount: number;
}

// Presentational only. T13 supplies the last readable position and mounts this.
export function ContinueReading({ to, courseName, title, pageLabel, pageCount, lastOpenedLabel, questionCount }: ContinueReadingProps) {
  return <Link to={to} className="continue-reading">
    <span className="reading-preview" aria-hidden="true"><span>{title}</span><span className="preview-lines" /><span className="preview-highlight" /><span className="preview-lines" /></span>
    <span className="reading-copy"><span className="metadata">Tiếp tục đọc · {courseName}</span><span className="reading-title">{title}</span><span className="metadata">Trang {pageLabel} / {pageCount} · mở lần cuối {lastOpenedLabel} · {questionCount} câu hỏi với trợ giảng</span></span>
    <span className="reading-action">Đọc tiếp</span>
  </Link>;
}
