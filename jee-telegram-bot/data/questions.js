// Reviewed MCQ batch: JEE Main 2024, 27 January, Shift 1.
// Question text and worked answers cross-checked against the cited solved paper.
// Official NTA final answer key for this date/shift is linked for audit.
const questions = [
  {
    id: "2024-jan27-shift1-maths-q7",
    verified: true,
    source_url: "https://image-static.collegedunia.com/public/questions/jee-main/2024/1792410752_JEE-Main-2024-Paper-1-B-E-B-Tech-Jan-27-Shift-1-Official-Question-Paper-PDF.pdf",
    answer_key_url: "https://nta.ac.in/download/notice/notice_20240212120843.pdf",
    year: "2024",
    shift: "27 January · Shift 1",
    subject: "maths",
    topic: "Three Dimensional Geometry",
    question: "Find the distance from P(7, −2, 11) to the line (x−6)/1 = (y−4)/0 = (z−8)/3, measured along the line (x−5)/2 = (y−1)/(−3) = (z−5)/6.",
    options: ["12", "18", "21", "14"],
    answer: 3,
    explanation: "A point on the second line is B = (2λ+5, −3λ+1, 6λ+5). Requiring B to lie on the first line gives λ = −1 and B = (3, 4, −1). Therefore PB = √[(7−3)²+(−2−4)²+(11+1)²] = √196 = 14."
  },
  {
    id: "2024-jan27-shift1-maths-q5",
    verified: true,
    source_url: "https://image-static.collegedunia.com/public/questions/jee-main/2024/1792410752_JEE-Main-2024-Paper-1-B-E-B-Tech-Jan-27-Shift-1-Official-Question-Paper-PDF.pdf",
    answer_key_url: "https://nta.ac.in/download/notice/notice_20240212120843.pdf",
    year: "2024",
    shift: "27 January · Shift 1",
    subject: "maths",
    topic: "Definite Integration",
    question: "Let (a,b) be the orthocentre of the triangle with vertices (1,2), (2,3), and (3,1). If I₁ = ∫ₐᵇ x sin(4x−x²) dx and I₂ = ∫ₐᵇ sin(4x−x²) dx, find 36(I₁/I₂).",
    options: ["80", "72", "66", "88"],
    answer: 1,
    explanation: "The orthocentre lies on x+y=4, so a+b=4. Since sin(x(4−x)) is unchanged by x→4−x, I₁ = ∫ₐᵇ(4−x)sin(x(4−x))dx. Adding this to the original I₁ gives 2I₁=4I₂, hence I₁/I₂=2 and 36(I₁/I₂)=72."
  },
  {
    id: "2024-jan27-shift1-maths-q19",
    verified: true,
    source_url: "https://image-static.collegedunia.com/public/questions/jee-main/2024/1792410752_JEE-Main-2024-Paper-1-B-E-B-Tech-Jan-27-Shift-1-Official-Question-Paper-PDF.pdf",
    answer_key_url: "https://nta.ac.in/download/notice/notice_20240212120843.pdf",
    year: "2024",
    shift: "27 January · Shift 1",
    subject: "maths",
    topic: "Binomial Theorem",
    question: "Let A be the sum of coefficients in (1−3x+10x²)ⁿ and B be the sum of coefficients in (1+x²)ⁿ. Which relation is true?",
    options: ["B = A³", "3A = B", "A = B³", "A = 3B"],
    answer: 2,
    explanation: "The sum of coefficients is found by setting x=1. Thus A=(1−3+10)ⁿ=8ⁿ and B=(1+1)ⁿ=2ⁿ. Therefore A=B³."
  },
  {
    id: "2024-jan27-shift1-maths-q16",
    verified: true,
    source_url: "https://image-static.collegedunia.com/public/questions/jee-main/2024/1792410752_JEE-Main-2024-Paper-1-B-E-B-Tech-Jan-27-Shift-1-Official-Question-Paper-PDF.pdf",
    answer_key_url: "https://nta.ac.in/download/notice/notice_20240212120843.pdf",
    year: "2024",
    shift: "27 January · Shift 1",
    subject: "maths",
    topic: "Sequences and Series",
    question: "How many common terms are there in the two arithmetic progressions 4, 9, 14, 19, ... (up to its 25th term) and 3, 6, 9, 12, ... (up to its 37th term)?",
    options: ["9", "8", "5", "7"],
    answer: 3,
    explanation: "The common terms are 9, 24, 39, 54, 69, 84 and 99. Both lists end before the next common term, so there are 7 common terms."
  },
  {
    id: "2024-jan27-shift1-maths-q13",
    verified: true,
    source_url: "https://image-static.collegedunia.com/public/questions/jee-main/2024/1792410752_JEE-Main-2024-Paper-1-B-E-B-Tech-Jan-27-Shift-1-Official-Question-Paper-PDF.pdf",
    answer_key_url: "https://nta.ac.in/download/notice/notice_20240212120843.pdf",
    year: "2024",
    shift: "27 January · Shift 1",
    subject: "maths",
    topic: "Three Dimensional Geometry",
    question: "The shortest distance between the lines (x−4)/1 = (y+1)/2 = z/(−3) and (x−λ)/2 = (y+1)/4 = (z−2)/(−5) is 6/√5. What is the sum of all possible values of λ?",
    options: ["10", "5", "7", "8"],
    answer: 3,
    explanation: "Using the skew-lines distance formula gives 6/√5 = |2(λ−4)|/√5. Hence |λ−4|=3, so λ=1 or 7 and their sum is 8."
  },
  {
    id: "2024-jan27-shift1-maths-q1",
    verified: true,
    source_url: "https://image-static.collegedunia.com/public/questions/jee-main/2024/1792410752_JEE-Main-2024-Paper-1-B-E-B-Tech-Jan-27-Shift-1-Official-Question-Paper-PDF.pdf",
    answer_key_url: "https://nta.ac.in/download/notice/notice_20240212120843.pdf",
    year: "2024",
    shift: "27 January · Shift 1",
    subject: "maths",
    topic: "Definite Integration",
    question: "If ∫₀¹ 1/(√(3+x)+√(1+x)) dx = a+b√2+c√3, where a,b,c are rational, find 2a+3b−4c.",
    options: ["4", "10", "7", "8"],
    answer: 3,
    explanation: "Rationalising gives one half of ∫₀¹[√(3+x)−√(1+x)]dx. Evaluating, the integral is 3−(2√2)/3−√3. Thus a=3, b=−2/3, c=−1 and 2a+3b−4c=8."
  }
];
export default questions;
