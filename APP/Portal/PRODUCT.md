# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

delegated: static HTML/CSS/JavaScript so the empty Portal surface can be previewed immediately and later embedded into the existing Django stack without introducing a second frontend runtime.

## Users

Sinh viên UTH, thường truy cập trong thời gian ngắn giữa các buổi học để kiểm tra lịch hôm nay, điểm, điểm danh và thông báo.

## Product Purpose

UTH Student Portal là lớp giao diện sinh viên kết nối với hệ thống quản lý và điểm danh nhận diện khuôn mặt hiện có. Thành công là sinh viên hiểu được trạng thái học tập trong vài giây và đi tới đúng chi tiết khi cần.

## Positioning

Backend là source of truth cho dữ liệu cá nhân, lịch học, điểm và điểm danh; portal ưu tiên khả năng quét nhanh, minh bạch trạng thái dữ liệu và không bịa chỉ số khi API chưa cung cấp.

## Operating Context

Portal vận hành cạnh ứng dụng quản lý Django và máy điểm danh OpenCV. Sinh viên dùng desktop, tablet và mobile; các luồng riêng gồm lịch học, điểm số, điểm danh, môn học, diễn đàn, tin nhắn, thông báo và hồ sơ.

## Capabilities and Constraints

- Phải tái sử dụng authentication và API hiện có khi tích hợp.
- Các vùng chưa có endpoint student-facing phải hiển thị trạng thái cần backend thay vì dữ liệu minh họa giả.
- Không mở rộng quyền chat, không expose face embedding, biometric template, secret hoặc dữ liệu riêng của sinh viên khác.
- Responsive từ 360px đến desktop lớn; semantic HTML, keyboard navigation, visible focus, ARIA và reduced motion là yêu cầu.

## Brand Commitments

Tên sản phẩm là UTH Student Portal. Visual direction là Academic Premium: sạch, hiện đại, chuyên nghiệp, đáng tin cậy, technical nhưng không cyberpunk. Logo UTH thật được reuse từ `APP/Máy điểm danh/assets/uth-logo.png`. Màu #0759A5 chỉ là màu UI provisional, không tuyên bố là màu thương hiệu chính thức.

## Evidence on Hand

- Django models tại `admin_check/portal/models.py`: Student, Subject, Schedule, AttendanceSession và AttendanceRecord.
- Các endpoint hiện có nằm trong `admin_check/portal/urls.py` và `views.py`, chủ yếu phục vụ management/kiosk.
- Logo thật tại `APP/Máy điểm danh/assets/uth-logo.png`.
- Chưa có API student portal cho grades, notifications, forum, messages hoặc dashboard tổng hợp.

## Product Principles

- Mở portal là hiểu ngay hôm nay có gì.
- Dữ liệu thật trước, trang trí sau.
- Trạng thái thiếu dữ liệu phải rõ ràng và có đường nối backend.
- Quyền riêng tư và quyền truy cập được enforce ở backend.

## Accessibility & Inclusion

WCAG-oriented implementation: contrast đủ dùng, focus rõ, labels và trạng thái được đọc bởi screen reader, thao tác mobile không phụ thuộc hover, hỗ trợ `prefers-reduced-motion`.
## Data integration

Student Portal is served by Django at `/student-portal/` and reads only the
authenticated student's records from the shared `AttendanceRecord` database.
Attendance is written by the Kiosk API and is never recreated or reclassified
in this frontend.
