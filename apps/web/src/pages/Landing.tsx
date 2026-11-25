import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Brand } from '@/components/Brand';
import { Button } from '@/components/ui/button';
import { homePath, useMe } from '@/features/auth';
import { ExampleAnswer } from '@/features/landing/ExampleAnswer';
import { LandingIcon } from '@/features/landing/LandingIcon';
import './landing.css';

const disclaimer = 'Phiên bản thử nghiệm, chưa phải hệ thống chính thức của trường.';
const attribution = 'Nội dung giáo trình thuộc các tác giả trên VOER; trích đoạn trên trang này giữ nguyên văn.';
const workflows = [
  { role: 'Sinh viên', steps: [
    'Đọc giáo trình của lớp',
    'Hỏi trợ giảng và mở nguồn để kiểm chứng',
    'Luyện tập, nộp bài',
    'Xem điểm, nhận xét và tiến độ của mình',
  ] },
  { role: 'Giảng viên', steps: [
    'Công bố, thay bản hoặc thu hồi học liệu (trợ giảng chỉ dùng bản đang công bố)',
    'Soạn câu luyện tập, giao bài tập',
    'Chấm, lưu nháp rồi công bố điểm',
    'Xem hoạt động và kết quả của lớp',
  ] },
];
const principles = [
  { icon: 'book', text: 'Chỉ dùng học liệu đã công bố của lớp bạn.' },
  { icon: 'source', text: 'Mỗi ý có số trang; bấm vào để mở đúng đoạn và tự đối chiếu.' },
  { icon: 'alert', text: 'Học liệu không đủ căn cứ thì trợ giảng nói rõ, không đoán.' },
] as const;
const privacy = [
  { icon: 'shield', text: 'Quyền xem học liệu kiểm tại máy chủ theo từng lớp.' },
  { icon: 'model', text: 'Câu hỏi và các đoạn học liệu liên quan được gửi tới mô hình ngôn ngữ do hệ thống cấu hình; tên mô hình hiện dưới mỗi câu trả lời. Bản demo trực tuyến có thể dùng nhà cung cấp mô hình bên ngoài.' },
  { icon: 'history', text: 'Lịch sử hỏi đáp chỉ người hỏi xem được trên giao diện.' },
] as const;
const faqs = [
  ['Làm sao có tài khoản?', 'Tài khoản do quản trị viên cấp cho sinh viên và giảng viên tham gia thử nghiệm; hệ thống không cho tự đăng ký.'],
  ['Trợ giảng có trả lời mọi câu hỏi?', 'Không. Trợ giảng chỉ dùng học liệu đã công bố của lớp bạn. Mỗi câu hỏi được xử lý độc lập, nên hãy hỏi đầy đủ ý.'],
  ['Câu trả lời có luôn đúng?', 'Không đảm bảo. Hãy mở nguồn trích dẫn để đối chiếu; nếu thấy sai, hãy hỏi giảng viên.'],
];

export function Landing() {
  const me = useMe();
  const destination = me.data ? homePath(me.data) : '/login';
  const label = me.data ? 'Vào lớp học' : 'Đăng nhập';
  const email = import.meta.env.VITE_SUPPORT_EMAIL?.trim();
  useEffect(() => {
    const previous = document.title;
    document.title = 'DUTLearn — Học theo lớp, từ giáo trình đến bài tập';
    return () => { document.title = previous; };
  }, []);

  return <div className="landing-page">
    <a className="skip-link" href="#landing-main">Bỏ qua đến nội dung chính</a>
    <header className="landing-header">
      <div className="landing-top landing-container">
        <Link to="/" className="landing-logo"><Brand /></Link>
        <nav className="landing-nav" aria-label="Điều hướng trang chủ">
          <a href="#cach-hoat-dong">Cách hoạt động</a>
          <a href="#hoi-dap">Câu hỏi thường gặp</a>
          <Button asChild className="landing-login"><Link to={destination}>{label}</Link></Button>
        </nav>
      </div>
    </header>
    <main id="landing-main" tabIndex={-1}>
      <section className="landing-hero" aria-labelledby="landing-title">
        <div className="landing-container landing-intro">
          <div className="landing-copy">
            <h1 id="landing-title">Học theo lớp, từ giáo trình đến bài tập</h1>
            <p className="landing-lead">Đọc học liệu giảng viên đã công bố, hỏi trợ giảng AI và mở đúng trang nguồn để đối chiếu; luyện tập, nộp bài và xem phản hồi trong cùng một nơi.</p>
            <div className="landing-actions">
              <Button asChild className="landing-primary"><Link to={destination}>{label}</Link></Button>
              <Button asChild className="landing-secondary"><a href="#cach-hoat-dong">Xem cách hoạt động</a></Button>
            </div>
            <p className="landing-disclaimer">Tài khoản do quản trị viên cấp · {disclaimer}</p>
          </div>
          <figure className="landing-product">
            <img src="/landing/reader-tutor.webp" width={1280} height={800} alt="Ảnh chụp màn hình: trang giáo trình bên trái, trợ giảng trả lời kèm số trang nguồn bên phải" />
            <figcaption>Ảnh chụp giao diện với dữ liệu minh họa · học phần Kỹ thuật lập trình</figcaption>
          </figure>
        </div>
      </section>
      <div className="landing-container">
        <section id="cach-hoat-dong" className="landing-section" aria-labelledby="landing-workflow-title">
          <h2 id="landing-workflow-title">Một lớp học phần trên DUTLearn</h2>
          <div className="landing-workflows">{workflows.map(({ role, steps }) => <article className="landing-workflow" key={role} aria-label={role}>
            <h3>{role}</h3>
            <ol>{steps.map(step => <li key={step}>{step}</li>)}</ol>
          </article>)}</div>
          <div className="landing-workflow-notes">
            <p>Quản trị viên cấp tài khoản, tạo lớp và ghi danh; không đọc nội dung lớp.</p>
            <p>Tiến độ chỉ ghi nhận hoạt động và kết quả thật, không dùng để đánh giá năng lực.</p>
          </div>
        </section>
        <section className="landing-section landing-tutor" aria-labelledby="landing-tutor-title">
          <div>
            <h2 id="landing-tutor-title">Trợ giảng có dẫn nguồn</h2>
            <ul className="landing-icon-list">{principles.map(({ icon, text }) => <li key={icon}><LandingIcon name={icon} /><p>{text}</p></li>)}</ul>
          </div>
          <ExampleAnswer />
        </section>
        <section className="landing-section" aria-labelledby="landing-privacy-title">
          <div className="landing-privacy">
            <h2 id="landing-privacy-title">Dữ liệu và quyền truy cập</h2>
            <ul className="landing-icon-list">{privacy.map(({ icon, text }) => <li key={icon}><LandingIcon name={icon} /><p>{text}</p></li>)}</ul>
          </div>
        </section>
        <section id="hoi-dap" className="landing-section" aria-labelledby="landing-faq-title">
          <h2 id="landing-faq-title">Câu hỏi thường gặp</h2>
          {faqs.map(([question, answer], index) => <details key={question} className="landing-faq">
            <summary>{question}</summary><p>{answer}</p>
            {index === 0 && email && <p>Liên hệ: <a href={`mailto:${email}`}>{email}</a></p>}
          </details>)}
        </section>
      </div>
    </main>
    <footer className="landing-footer landing-container">
      <p>Đồ án tốt nghiệp · Trường ĐH Bách khoa – ĐH Đà Nẵng · Khoa CNTT</p>
      <p>{disclaimer}</p>
      <p>Học phần Kỹ thuật lập trình · <em>Giáo trình Lập trình căn bản</em> (VOER) · <a href="https://creativecommons.org/licenses/by/3.0/">CC BY 3.0</a></p>
      <p>{attribution}</p>
    </footer>
  </div>;
}
