import { Link } from 'react-router-dom';

export interface ContinueReadingProps {
  to: string;
  courseName: string;
  title: string;
  pageLabel: string;
  pageCount?: number;
  lastOpenedLabel: string;
  questionCount?: number;
}

// Presentational only. T13 supplies the last readable position and mounts this.
export function ContinueReading({ to, courseName, title, pageLabel }: ContinueReadingProps) {
  return <Link to={to} className="continue-reading">
    <span className="reading-copy"><span className="reading-eyebrow">Tiếp tục đọc</span><span className="reading-title">{title}</span><span className="metadata">{courseName} · Bạn dừng ở trang {pageLabel}</span></span>
    <span className="reading-action">Đọc tiếp</span>
  </Link>;
}
