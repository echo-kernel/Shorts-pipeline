// First reviewed MCQ batch: JEE Main 2024, 27 January, Shift 1.
// Question text/options/solutions cross-checked against the cited solved paper;
// the official NTA final key for this date and shift is linked for audit.
// Keep numerical-answer questions out until the bot supports that format.
const questions = [
  {
    id: "2024-jan27-shift1-maths-q1",
    verified: true,
    source_url: "https://www.ayjr.in/wp-content/uploads/JEE-Mains-2024-Shift-1-Question-Paper-27-Jan.pdf",
    answer_key_url: "https://nta.ac.in/download/notice/notice_20240212120843.pdf",
    year: "2024",
    shift: "27 January · Shift 1",
    subject: "maths",
    topic: "Binomial Coefficients",
    question: "For non-negative integers n and r, the relation (n−1)C(r) = (k²−8)·nC(r+1) holds. Which range of k is possible?",
    options: [
      "2√2 < k ≤ 3",
      "2√3 < k ≤ 3√2",
      "2√3 < k < 3√3",
      "2√2 < k < 2√3"
    ],
    answer: 0,
    explanation: "Using the ratio (n−1)C(r) / nC(r+1) = (r+1)/n, we get k²−8 = (r+1)/n. Since 0 < (r+1)/n ≤ 1, 8 < k² ≤ 9. Thus 2√2 < k ≤ 3."
  },
  {
    id: "2024-jan27-shift1-maths-q2",
    verified: true,
    source_url: "https://www.ayjr.in/wp-content/uploads/JEE-Mains-2024-Shift-1-Question-Paper-27-Jan.pdf",
    answer_key_url: "https://nta.ac.in/download/notice/notice_20240212120843.pdf",
    year: "2024",
    shift: "27 January · Shift 1",
    subject: "maths",
    topic: "Three Dimensional Geometry",
    question: "Find the distance from P(7, −2, 11) to the line (x−6)/1 = (y−4)/0 = (z−8)/3, measured along the line (x−5)/2 = (y−1)/(−3) = (z−5)/6.",
    options: ["12", "14", "18", "21"],
    answer: 1,
    explanation: "A point on the second line is B = (2λ+5, −3λ+1, 6λ+5). Requiring B to lie on the first line gives −3λ−3 = 0, so λ = −1 and B = (3, 4, −1). Therefore PB = √[(7−3)²+(−2−4)²+(11+1)²] = √196 = 14."
  },
  {
    id: "2024-jan27-shift1-maths-q4",
    verified: true,
    source_url: "https://www.ayjr.in/wp-content/uploads/JEE-Mains-2024-Shift-1-Question-Paper-27-Jan.pdf",
    answer_key_url: "https://nta.ac.in/download/notice/notice_20240212120843.pdf",
    year: "2024",
    shift: "27 January · Shift 1",
    subject: "maths",
    topic: "Definite Integration",
    question: "Let (a,b) be the orthocentre of the triangle with vertices (1,2), (2,3), and (3,1). If I₁ = ∫ₐᵇ x sin(4x−x²) dx and I₂ = ∫ₐᵇ sin(4x−x²) dx, find 36(I₁/I₂).",
    options: ["72", "88", "80", "66"],
    answer: 0,
    explanation: "The orthocentre lies on x+y=4, so a+b=4. Since sin(x(4−x)) is unchanged by x→4−x, I₁ = ∫ₐᵇ(4−x)sin(x(4−x))dx. Adding this to the original I₁ gives 2I₁=4I₂, hence I₁/I₂=2 and 36(I₁/I₂)=72."
  },
  {
    id: "2024-jan27-shift1-maths-q5",
    verified: true,
    source_url: "https://www.ayjr.in/wp-content/uploads/JEE-Mains-2024-Shift-1-Question-Paper-27-Jan.pdf",
    answer_key_url: "https://nta.ac.in/download/notice/notice_20240212120843.pdf",
    year: "2024",
    shift: "27 January · Shift 1",
    subject: "maths",
    topic: "Binomial Theorem",
    question: "Let A be the sum of coefficients in (1−3x+10x²)ⁿ and B be the sum of coefficients in (1+x²)ⁿ. Which relation is true?",
    options: ["A = B³", "3A = B", "B = A³", "A = 3B"],
    answer: 0,
    explanation: "The sum of coefficients is found by setting x=1. Thus A=(1−3+10)ⁿ=8ⁿ and B=(1+1)ⁿ=2ⁿ. Therefore A=B³."
  }
];
export default questions;
