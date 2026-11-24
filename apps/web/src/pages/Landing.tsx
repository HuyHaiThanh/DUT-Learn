import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Brand } from '@/components/Brand';
import { Button } from '@/components/ui/button';
import { homePath, useMe } from '@/features/auth';
import { ExampleAnswer } from '@/features/landing/ExampleAnswer';
import './landing.css';

const disclaimer = 'Phiên bản thử nghiệm, chưa phải hệ thống chính thức của trường.';
const attribution = 'Nội dung giáo trình thuộc các tác giả trên VOER; trích đoạn trên trang này giữ nguyên văn.';
const steps = [
  ['Giảng viên công bố học liệu', 'Tài liệu chỉ đến với sinh viên và trợ giảng sau khi giảng viên công bố; thu hồi là trợ giảng thôi dùng ngay.'],
  ['Sinh viên đọc và hỏi ngay cạnh trang', 'Trợ giảng nằm cạnh trang đang đọc, có chế độ trả lời trực tiếp và dẫn dắt từng bước.'],
  ['Mở nguồn để kiểm chứng', 'Mỗi ý có số trích dẫn; bấm vào là mở đúng trang và đoạn đã dùng.'],
];
const faqs = [
  ['Làm sao có tài khoản?', 'Tài khoản do quản trị viên cấp cho sinh viên và giảng viên tham gia thử nghiệm; hệ thống không cho tự đăng ký.'],
  ['Trợ giảng có trả lời mọi câu hỏi?', 'Không. Trợ giảng chỉ dùng học liệu đã công bố của lớp bạn. Mỗi câu hỏi được xử lý độc lập, nên hãy hỏi đầy đủ ý.'],
  ['Câu hỏi của tôi được gửi đi đâu?', 'Câu hỏi và các đoạn học liệu liên quan được gửi tới mô hình ngôn ngữ để soạn câu trả lời. Trên bản demo trực tuyến, mô hình do nhà cung cấp bên ngoài vận hành; tên mô hình hiện dưới mỗi câu trả lời. Lịch sử hỏi đáp chỉ bạn xem được.'],
  ['Câu trả lời có luôn đúng?', 'Không đảm bảo. Vì vậy mỗi ý đều có nguồn để bạn mở và đối chiếu; nếu thấy sai, hãy hỏi giảng viên.'],
];
export function Landing() {
  const me = useMe();
  const destination = me.data ? homePath(me.data) : '/login';
  const label = me.data ? 'Vào trang học tập' : 'Đăng nhập';
  const email = import.meta.env.VITE_SUPPORT_EMAIL?.trim();
  useEffect(() => {
    const previous = document.title;
    document.title = 'DUTLearn — Học theo giáo trình với trợ giảng có dẫn nguồn';
    return () => { document.title = previous; };
  }, []);
  return <div className="landing-page">
    <a className="skip-link" href="#landing-main">Bỏ qua đến nội dung chính</a>
    <div className="landing-hero"><header className="landing-top landing-container"><Link to="/" className="landing-logo"><Brand /></Link><nav className="landing-nav" aria-label="Điều hướng trang chủ"><a href="#cach-hoat-dong">Cách hoạt động</a><a href="#hoi-dap">Câu hỏi thường gặp</a></nav><Button asChild className="landing-login"><Link to={destination}>{label}</Link></Button></header>
      <div className="landing-container landing-intro"><h1>Đọc giáo trình, hỏi trợ giảng, mở đúng trang để kiểm chứng</h1><p>DUTLearn là nền tảng học tập theo lớp học phần. Trợ giảng AI chỉ trả lời từ học liệu giảng viên đã công bố cho lớp, kèm số trang và đoạn nguồn; khi học liệu không đủ căn cứ, trợ giảng nói rõ thay vì đoán.</p>
        <div className="landing-actions"><Button className="landing-primary" onClick={() => { const heading = document.getElementById('landing-example-title'); heading?.scrollIntoView({ block: 'start' }); heading?.focus({ preventScroll: true }); }}>Xem một câu trả lời mẫu</Button><Button asChild className="landing-secondary"><Link to={destination}>{label}</Link></Button></div><p className="landing-disclaimer">{disclaimer}</p>
      </div>
    </div>
    <main id="landing-main" className="landing-container" tabIndex={-1}><ExampleAnswer />
      <section id="cach-hoat-dong" className="landing-section"><h2>Cách hoạt động</h2><ol className="landing-steps">{steps.map(([title, text]) => <li key={title}><h3>{title}</h3><p>{text}</p></li>)}</ol><div className="landing-roles"><p>Sinh viên: đọc, hỏi, luyện tập theo lớp</p><p>Giảng viên: quản lý học liệu và bài học của lớp mình</p><p>Quản trị viên: tài khoản, học phần, lớp và ghi danh — không đọc nội dung lớp</p></div></section>
      <section className="landing-section"><h2>Học phần thí điểm</h2><div className="landing-pilot"><h3>Kỹ thuật lập trình</h3><p>Giáo trình: <em>Giáo trình Lập trình căn bản</em> (VOER), 201 trang, nội dung C.</p><a href="https://creativecommons.org/licenses/by/3.0/">Giấy phép CC BY 3.0</a><p className="landing-note">{attribution}</p></div></section>
      <section id="hoi-dap" className="landing-section"><h2>Câu hỏi thường gặp</h2>{faqs.map(([question, answer], index) => <details key={question} className="landing-faq"><summary>{question}</summary><p>{answer}</p>{index === 0 && email && <p>Liên hệ: <a href={`mailto:${email}`}>{email}</a></p>}</details>)}</section>
    </main>
    <footer className="landing-footer landing-container"><p>Đồ án tốt nghiệp · Trường Đại học Bách khoa, Đại học Đà Nẵng · Khoa Công nghệ Thông tin</p><p>{disclaimer}</p><p>{attribution}</p></footer>
  </div>;
}
