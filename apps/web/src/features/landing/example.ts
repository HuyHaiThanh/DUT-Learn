export interface ExampleSource { id: number; page: string; text: string; highlight: string }
export interface RecordedExample { recordedAt: string; model: string; material: string; question: string; answer: string; sources: ExampleSource[]; refusalQuestion: string; refusal: string }

export const example: RecordedExample = {
  recordedAt: '2026-11-22',
  model: 'Qwen2.5-7B-Instruct',
  material: 'Giáo trình Lập trình căn bản',
  question: 'Hàm đệ quy là gì?',
  answer: `Hàm đệ quy là một hàm được gọi là chính nó trong quá trình thực hiện. Định nghĩa chính của hàm đệ quy bao gồm hai phần chính:

- Phần dừng hay trường hợp nguyên tố: Đây là trường hợp cơ bản nhất mà hàm đệ quy không cần gọi chính nó nữa. Ví dụ trong ví dụ về tính giai thừa, trường hợp dừng là khi n=0, vì 0! = 1 [1].

- Phần đệ quy: Đây là phần của hàm mà trong đó hàm gọi chính nó với tham số đã được thay đổi. Trong ví dụ về tính giai thừa, phần đệ quy là n>0 thì n! = n * (n-1)! [2].`,
  sources: [
    {
      id: 1, page: '110',
      text: `HÀM ĐỆ QUY
Định nghĩa
Một hàm được gọi là đệ quy nếu bên trong thân hàm có lệnh gọi đến chính nó.
Ví dụ: Người ta định nghĩa giai thừa của một số nguyên dương n như sau:
n!=1* 2 * 3 *…* (n-1) *n = (n-1)! *n (với 0!=1)
Như vậy, để tính n! ta thấy nếu n=0 thì n!=1 ngược lại thì n!=n * (n-1)!`,
      highlight: `Như vậy, để tính n! ta thấy nếu n=0 thì n!=1 ngược lại thì n!=n * (n-1)!`,
    },
    {
      id: 2, page: '112',
      text: `Đặc điểm cần lưu ý khi viết hàm đệ quy
- Hàm đệ quy phải có 2 phần:
• Phần dừng hay phải có trường hợp nguyên tố. Trong ví dụ ở trên thì trường hợp n=0 là trường hợp nguyên tố.
• Phần đệ quy: là phần có gọi lại hàm đang được định nghĩa. Trong ví dụ trên thì phần đệ quy là n>0 thì n! = n * (n-1)!
- Sử dụng hàm đệ quy trong chương trình sẽ làm chương trình dễ đọc, dễ hiểu và vấn đề được nêu bật rõ ràng hơn. Tuy nhiên trong đa số trường hợp thì hàm đệ quy tốn bộ nhớ nhiều hơn và tốc độ thực hiện chương trình chậm hơn không đệ quy.`,
      highlight: `• Phần dừng hay phải có trường hợp nguyên tố. Trong ví dụ ở trên thì trường hợp n=0 là trường hợp nguyên tố.
• Phần đệ quy: là phần có gọi lại hàm đang được định nghĩa. Trong ví dụ trên thì phần đệ quy là n>0 thì n! = n * (n-1)!`,
    },
  ],
  refusalQuestion: 'Giải thích cơ chế thu gom rác (garbage collection) của Java.',
  refusal: 'Học liệu của lớp chưa đủ căn cứ để trả lời câu hỏi này. Bạn có thể diễn đạt lại câu hỏi cụ thể hơn hoặc hỏi giảng viên.',
};
