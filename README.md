# Codex ↔ Blender

Công cụ MCP chạy trên máy để Codex biến prompt và nội dung bạn cung cấp thành cảnh Blender, ảnh xem trước và video MP4. Không cần OpenAI API key riêng: Codex đang kết nối là phần hiểu yêu cầu; Blender là phần dựng và render.

Luồng hoạt động: **prompt/nội dung trong Codex → mô tả cảnh JSON → Blender → PNG + .blend + MP4**.

## Giao diện tạo video — Frame Studio

Font, nhạc/âm lượng, lựa chọn voice, tỷ lệ khung hình, độ phân giải, FPS, samples và các lựa chọn tạo asset được tự lưu khi người dùng thay đổi. Mặc định video nằm trong `studio-data/preferences.json`, độc lập với từng dự án; kết quả AI và việc mở dự án cũ không ghi đè mặc định này. Trình duyệt giữ các thay đổi chưa đồng bộ để khôi phục nếu đóng trang ngay hoặc máy chủ cũ đang bận; lần kết nối máy chủ mới tiếp theo sẽ đồng bộ. Dự án mới dùng các lựa chọn đã lưu.

### Tạo asset từ ảnh

Tab **Tạo asset từ ảnh** nhận 1–4 ảnh PNG/JPG của cùng một đối tượng, tên asset, mô tả bổ sung và phong cách. Codex phân tích ảnh thật; Blender dựng mô hình bằng hình học 3D, render preview rồi xuất GLB tĩnh có vật liệu vào thư viện. Có thể tải GLB/file Blender hoặc bấm **Dùng trong dự án** để ưu tiên mô hình trong video hiện tại.

Chọn **Nhiều asset từ một ảnh** nếu ảnh chứa nhiều đồ vật. Chọn tối đa 5/10/20/40 món, nhập tên bộ assets và thêm đúng một ảnh. Có thể ghi tên các món cần lấy trong phần chi tiết hoặc để trống để tự nhận diện. Các góc nhìn trùng của cùng đồ vật được gộp lại; mỗi món có GLB, preview và file Blender riêng. Tiến trình và lỗi hiển thị theo từng món; những món thành công vẫn được giữ trong thư viện khi món khác lỗi.

Đây là bản diễn giải hình dáng/màu sắc từ ảnh, phù hợp với vật thể có cấu trúc rõ; không phải quét 3D hay bảo đảm tái tạo chính xác các mặt khuất. Các ảnh đầu vào được gửi tới Codex khi bấm dựng. Tác vụ và log được lưu trên máy, có thể theo dõi sau khi tải lại trang; tác vụ bị ngắt khi server khởi động lại có thể lấy lại đầu vào để thử lại.

Kiểm tra luồng Blender/GLB bằng `python scripts/smoke_assetgen.py`. Thêm `--live` để thử Codex với ảnh tổng hợp do bài test tự render. `python scripts/qa_assetgen_browser.py` kiểm tra giao diện trên server test cổng 8766 bằng Chrome và Playwright.

Chạy `start-studio.cmd` (nhấp đúp trên Windows), rồi mở **http://127.0.0.1:8765**. Hoặc chạy:

```powershell
.\.venv\Scripts\python.exe -m codex_blender.cli studio
```

Ứng dụng chạy trên máy, không cần đưa lên dịch vụ hosting. `start-studio.cmd` tự khởi động server nền và mở trình duyệt; chạy lại sẽ dùng server đã có. Nếu chạy lệnh CLI trực tiếp thì giữ cửa sổ Terminal mở khi sử dụng. Codex CLI phải được đăng nhập (`codex.cmd login status`). Log và PID của server nền ở `studio-data/server.log` và `studio-data/server.pid`.

Trong Studio:

Theo yêu cầu hiện tại, video xuất từ Studio chỉ phát **một track nhạc nền duy nhất** xuyên suốt. Chọn file trong tab Âm thanh hoặc để tool tổng hợp một nền nhạc đơn giản; file ngắn được lặp đến hết video. Voice, âm thanh upload khác và hiệu ứng đều bị loại khỏi bản xuất; không gọi dịch vụ TTS. Lời thoại vẫn có thể dùng làm nội dung phụ đề với mốc ước tính. Các hàm/API voice cũ được giữ lại, còn điều khiển voice trong trình dựng được ẩn.

Thư viện mới **Universal Core & Interior** có 180 asset từ hai ảnh tham khảo mới, tại `assets/generated/universal-interior-v1/`. Mỗi món có GLB, BLEND chỉnh sửa được, PNG và metadata; các mesh được đặt tên riêng, gốc giữa đáy. Mở `catalog.html` hoặc tìm `universal-interior-v1` trong Thư viện assets. Bộ khối, cơ khí, nội thất và bảy diorama là các diễn giải 3D theo ảnh, tĩnh và chưa có rig nhân vật. Thư viện cũ vẫn được giữ nguyên.

1. Tạo dự án, nhập một **prompt tổng** gồm nội dung, vật thể, bối cảnh và hành động; có thể nhập file `.txt`. Trong tab Prompt có thể thêm tối đa 4 ảnh tham khảo cho nội dung và bố cục.
2. Bấm **Tạo video**: tool đọc prompt và kiểm kê toàn bộ thư viện model, chuẩn bị từng vật thể/bối cảnh trước khi viết kịch bản. Ưu tiên model hoàn chỉnh; nếu thiếu thì tự dựng bổ sung theo model và các khối Core đã có. Có thể đổi màu/vật liệu, tạo băng trong suốt, thực phẩm hỏng, tách cửa/chi thể thành phần chuyển động và tạo rig xương thật. Phần còn thiếu được tự sinh, xuất GLB, BLEND và preview vào `assets/generated/auto-prepared/` trước khi viết kịch bản; chỉ lỗi dựng/xuất thực sự mới dừng luồng. Mỗi món giữ model hoàn chỉnh, các GLB bộ phận và recipe/rig để dùng lại. Bảng **Bộ assets** hiển thị các món đang tự dựng. Tab Phong cách và lựa chọn GLB ưu tiên đã được bỏ; tool tự chọn từ thư viện cho mỗi video.
3. Mô tả lời thoại, giọng đọc, nhạc và hiệu ứng âm thanh trong prompt tổng. Chế độ **Theo prompt** tự lấy lời đọc và các mốc của từng cảnh, tạo giọng tiếng Việt/Anh và phụ đề theo từng đoạn. Các điều khiển voice thủ công phục vụ cảnh cũ; phân cảnh mới dùng âm thanh đã biên soạn từ prompt.
4. Tỷ lệ, độ phân giải và FPS trong prompt được ưu tiên; nếu không ghi thì dùng giá trị ở **Xuất video**. Giữ nguyên các mốc phân cảnh/lời thoại đã ghi; suy ra thời lượng khi không có mốc (tối đa 3600 giây). Nhận cả khoảng thời lượng: **90–120 giây** cùng timeline kết thúc **01:35** sẽ tạo video **95 giây**, giữ đủ các phân cảnh. Nếu chỉ có khoảng, AI chọn thời lượng trong khoảng đó. Lời đọc không bị cắt ngầm để ép vào cảnh: nếu không thể đọc kịp, ứng dụng báo rõ đoạn cần chỉnh.
5. Bấm **Tạo video** để biên soạn toàn bộ timeline, dựng bối cảnh và chuyển động của từng cảnh, tạo âm thanh rồi render MP4. Danh sách **Phân cảnh theo prompt** cho xem mốc thời gian, hành động và lời thoại. Mỗi hành động phải gắn với đối tượng có chuyển động; chỉ di chuyển camera không đủ. Nếu prompt hoặc đầu vào dựng đã đổi, bấm xuất/preview sẽ lập kế hoạch mới thay vì dùng lại cảnh cũ.
6. Khi Blender đang render, thanh tiến trình hiển thị **phần trăm và số khung hình**. Bấm **Tạm dừng** để dừng sau khung hình đang xử lý; **Tiếp tục** dựng tiếp và giữ các khung đã xong. Thời gian tạm dừng không tính vào giới hạn thời gian render. Nút này có trong giai đoạn chờ/render, trước bước ghép MP4; bước lập kế hoạch và tạo âm thanh chỉ hiển thị trạng thái xử lý.

Prompt và ảnh tham khảo được gửi tới Codex bằng CLI đã đăng nhập trên máy. Dịch vụ voice online dùng `edge-tts` (Microsoft Edge) hoặc ElevenLabs theo giọng đã chọn, cần Internet. Giọng clone VoiceStudio đã đăng ký dùng bộ tạo giọng và model cài trên máy. Voice/nhạc được ghép trên máy. Ứng dụng có thể tổng hợp nhạc nền đơn giản và hiệu ứng hoạt hình (chuông, bước chân, máy móc, click, quét, gió, thở, pop) theo timeline; dùng file trong thư viện khi cần bản thu cụ thể.

Đã thêm giọng ElevenLabs **`gb30mYs9RQJGV3jqCOM2`** vào **Âm thanh → Giọng đọc ưu tiên**, dùng được cho **Theo prompt**, **Voice AI** và **Nghe thử giọng**. Chọn giọng này để dùng cho người thuyết minh chính; yêu cầu giọng cụ thể trong prompt được ưu tiên. Tích hợp dùng [Text to Speech API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert) với model `eleven_flash_v2_5` có hỗ trợ tiếng Việt ([danh sách model](https://elevenlabs.io/docs/overview/models)). Lời đọc được gửi tới ElevenLabs và sử dụng hạn mức của tài khoản; tài khoản/API key phải có quyền truy cập voice ID này.

Giọng Microsoft Edge tự kết nối lại tối đa 5 lần khi dịch vụ ngắt kết nối hoặc chưa trả âm thanh, với tổng thời gian chờ tối đa 120 giây. Giữ nguyên giọng, lời đọc, tốc độ và mốc từ của phụ đề. Nghe thử cùng nội dung/giọng/tốc độ dùng lại file đã tạo thành công để giảm phụ thuộc kết nối.

Studio gọi **ElevenLabs CLI** cho cả nghe thử, voice video và mốc từ của phụ đề. Cài CLI một lần trong workspace rồi đăng nhập:

```powershell
npm.cmd install --prefix studio-data/tools/elevenlabs @elevenlabs/cli@1.14.2
npx.cmd -y @elevenlabs/cli@latest onboard init
.\start-studio.cmd
```

CLI lưu key trong `.env` đã được Git bỏ qua. Studio đọc key ở phía server và truyền vào môi trường tiến trình CLI, không đưa key vào lệnh, dự án hoặc trình duyệt. Key mới từ CLI thay key cũ trong Cài đặt; nếu lưu key khác trong Cài đặt sau đó thì key vừa lưu được ưu tiên. Có thể đặt `ELEVENLABS_CLI_PATH` để dùng binary ở vị trí khác. Các giọng Microsoft Edge vẫn dùng được khi chưa cấu hình ElevenLabs.

Lỗi `paid_plan_required` nghĩa là gói tài khoản chưa có quyền dùng giọng thư viện qua API/CLI, khác với `quota_exceeded` (hết credits). Chuyển sang CLI không thay đổi quyền của gói tài khoản và không tự chọn giọng khác.

Đăng ký một giọng clone từ file mẫu bằng lệnh `.venv\Scripts\python.exe -m codex_blender.voice_clones --name "Tuấn Anh" --sample "ĐƯỜNG_DẪN_FILE_MẪU.mp3"`. Lệnh dùng ElevenLabs CLI, giữ bản sao mẫu trong `studio-data/voice-samples` và lưu trạng thái trong `studio-data/voice-clones.json`. Chỉ giọng có voice ID thật và không cần xác minh mới được chọn để tạo speech. Nếu tài khoản chưa có quyền Instant Voice Cloning, giọng xuất hiện ở trạng thái **Chưa clone**; chạy lại lệnh khi có quyền phù hợp sẽ cập nhật cùng mục giọng, không thêm mục trùng. Key và file mẫu không được gửi tới Codex.

Giọng **Tuấn Anh** trong workspace này đã được chuyển sang VoiceStudio local, dùng mẫu người dùng cung cấp. Chọn **Âm thanh → Giọng đọc ưu tiên → Tuấn Anh**, rồi **Nghe thử giọng**. Bộ cài, model Q8, file mẫu WAV và bản chép lời nằm trong `D:\VoiceStudio`; không cần mở ứng dụng VoiceStudio hoặc đăng nhập ElevenLabs. Studio gọi trực tiếp binary OmniVoice GGUF đi kèm VoiceStudio bằng Vulkan trên GPU, tạo từng đoạn tuần tự để hạn chế thiếu bộ nhớ. Cấu hình đường dẫn riêng nằm trong mục `local` của `studio-data/voice-clones.json`, không gửi tới trình duyệt. Giữ thư mục trên ổ D khi di chuyển workspace. Model GGUF hiện tại chỉ dành cho mục đích phi thương mại theo [tài liệu engine VoiceStudio](https://github.com/debpalash/VoiceStudio/blob/v0.5.8/docs/engines/omnivoice-gguf.md). Engine chưa trả mốc từ; phụ đề dùng thời gian ước tính. Kiểm tra thực tế nút nghe thử và giải mã âm thanh bằng `.venv\Scripts\python.exe scripts/qa_local_voice_browser.py` khi Studio đang chạy.

Luồng dựng hỗ trợ nhiều cảnh 3D, nhóm bộ phận có khớp/pivot, transform, xuất hiện/ẩn đối tượng, camera keyframes và ánh sáng riêng từng cảnh. Mô hình GLB tĩnh không tự có rig; AI phải dựng bộ phận tách rời cho động tác cần khớp. Yêu cầu vượt khả năng dựng/âm thanh được báo lỗi thay vì âm thầm bỏ cảnh. Việc kiểm tra timeline và chuyển động không bảo đảm mọi chi tiết hình ảnh được diễn giải chính xác; xem preview trước khi render chất lượng cao.

Trước khi dựng, AI liệt kê các yếu tố hình ảnh từ prompt: bối cảnh, nhân vật, đạo cụ, diện mạo và số lượng bộ phận. Mỗi yếu tố/bộ phận phải gắn với hình khối Blender thật; ảnh tham khảo không được dùng thay mô hình. Công thức `repeat` lặp cả nhóm và các phần con để dựng đủ tầng, bậc thang, cửa sổ, lan can mà không phải rút gọn thành một khối lớn. Các hành động phải tác động đúng nhân vật/đạo cụ được liệt kê. Thời lượng khai báo trong kịch bản được ưu tiên hơn câu yêu cầu thử ngắn còn lưu từ trước. Bản thử ngắn chỉ áp dụng khi prompt không khai báo thời lượng đầy đủ. Kéo dài một cảnh mở đầu không thể thay thế toàn bộ các cảnh trong timeline. Giao diện hiển thị phân cảnh ngay khi biên soạn xong, trong lúc Blender đang được dựng.

### Thư viện dùng lại

- **Cài đặt → Thư mục assets cố định:** chọn bằng hộp thoại hoặc dán đường dẫn tuyệt đối tới thư mục có sẵn. Mặc định là `assets/` của workspace.
- Upload, file TTS tạo thành công, GLB xuất từ Blender và ảnh thumbnail được lưu trong thư mục đó. Tên/mô tả/tags nằm trong file `.asset.json` bên cạnh GLB để AI tìm và chọn lại.
- Sau khi preview hoặc render hoàn tất, bấm **Lưu asset**; đặt tên, mô tả và chọn các đối tượng cần nhóm. Tool xuất GLB tĩnh, giữ chất liệu, đưa gốc tọa độ về giữa đáy và tạo thumbnail.
- Toàn bộ thư viện model được tự động xét cho mỗi prompt mới, không giới hạn ở 200 mục đầu. Kịch bản chỉ dùng bộ assets đã chuẩn bị, kể cả phần tự dựng bổ sung; các bước dựng cảnh và render kiểm tra lại đường dẫn, số lượng và rig. Catalog cũng được cung cấp cho Codex qua MCP `list_assets`. Nhân vật có các mesh rời có thể được tách theo tên bộ phận, đặt pivot và gắn skeleton với rigid weights; recipe giữ các bộ phận để điều khiển tay/chân/biểu cảm ở bước dựng cảnh.
- Đã lưu sẵn **Nhà phát minh áo vàng** và **Tòa nhà 10 tầng cắt lớp** từ video mẫu vào `assets/generated/` trong workspace này.
- Đổi thư mục không di chuyển hoặc xóa tài nguyên cũ. Các render đang chạy giữ nguyên thư mục đã chụp lúc bắt đầu; dự án cũ có thể cần chọn lại tài nguyên nếu thư viện đổi.

Dự án được lưu trong `studio-data/projects/`; cài đặt thư viện ở `studio-data/settings.json`; render vẫn nằm trong `outputs/`. Các dữ liệu cục bộ này được bỏ qua bởi Git. Nhấn **Lưu dự án** trước khi đóng để giữ phần chỉnh sửa mới.

Nếu render bị ngắt, bấm **Tiếp tục render** để chạy lại job đã lưu: giữ nguyên cảnh, âm thanh và thư mục assets của job, bỏ qua các khung PNG hoàn chỉnh, dựng lại các khung thiếu hoặc bị ghi dở rồi ghép MP4. **Xem render.log** mở log; lần chạy tiếp được nối vào log cũ. Thay đổi prompt hoặc cấu hình chỉ áp dụng khi tạo một job mới.

### Kiểm thử Studio

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
# Cần server tại 8766 và Chrome để chạy kiểm thử trình duyệt:
.\.venv\Scripts\python.exe scripts/qa_studio_browser.py http://127.0.0.1:8766
# Kiểm tra nút tạm dừng và tiến trình trên desktop/mobile bằng API giả lập, cần Chrome:
.\.venv\Scripts\python.exe -m scripts.qa_studio_pause
# Dùng các GLB đã seed để kiểm tra render + mix audio thật:
.\.venv\Scripts\python.exe scripts/smoke_studio_media.py
# Kiểm tra AI thật (gửi một prompt và ảnh mẫu, dùng hạn mức Codex):
.\.venv\Scripts\python.exe scripts/smoke_studio_planner.py
```

Đã kiểm tra 12 bài test, giao diện desktop/mobile bằng Chrome, xuất 2 GLB từ Blender, render dùng lại GLB với âm thanh/phụ đề, và Codex lập cảnh thật với ảnh tham khảo. Kiểm thử âm thanh dùng tín hiệu mẫu để xác nhận đường trộn; chất lượng voice riêng phụ thuộc file bạn cung cấp. Tham khảo [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) và [edge-tts](https://github.com/rany2/edge-tts).

## Cài đặt trên Windows

Yêu cầu Python 3.11+, Codex có hỗ trợ MCP, Blender 4.2+ (khuyến nghị thử bản bạn đang dùng bằng smoke test). FFmpeg được cung cấp qua thư viện Python.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

`requirements.lock` khóa các thư viện đã kiểm thử trên Windows. Có thể cài bằng `pip install -r requirements.lock` rồi `pip install --no-deps -e .`. Nếu pip gặp lỗi `InvalidChunkLength` trong môi trường mạng này, dùng `uv --system-certs pip install --python .venv/Scripts/python.exe -e .` (cần cài uv trước).

Cài Blender từ https://www.blender.org/download/. Tool tự tìm Blender trong PATH và `C:\Program Files\Blender Foundation`. Nếu cài ở nơi khác, đặt biến môi trường trước khi mở Codex:

```powershell
$env:BLENDER_PATH = 'D:\Apps\Blender\blender.exe'
.\.venv\Scripts\python.exe -m codex_blender.cli doctor
```

Hoặc dùng Blender headless qua gói `bpy` trong chính môi trường Python (chỉ khi có wheel phù hợp Python/hệ điều hành):

```powershell
.\.venv\Scripts\python.exe -m pip install bpy
```

## Kết nối Codex

Chạy từ workspace này; lệnh đăng ký server vào cấu hình Codex của tài khoản hiện tại:

```powershell
codex.cmd mcp add blender -- 'C:\Users\thanh\Documents\codex-blender\.venv\Scripts\python.exe' -m codex_blender.server
```

Nếu cần đường dẫn Blender tùy chỉnh, thêm `--env 'BLENDER_PATH=D:\Apps\Blender\blender.exe'` trước `--`. Mở lại phiên Codex để nạp server. Kiểm tra bằng `codex.cmd mcp list`. Có thể gỡ bằng `codex.cmd mcp remove blender`.

Dùng `codex.cmd` trên Windows để tránh lỗi PowerShell chặn file `codex.ps1`. File `scripts/connect-codex.ps1` cũng chứa lệnh đăng ký với đường dẫn tự động.

## Sử dụng bằng prompt

Sau khi kết nối, nhắn Codex:

> Dùng tool blender tạo video 5 giây, tỉ lệ 16:9: khối lập phương xanh xoay trong vòng kim loại vàng, nền studio tối. Tiêu đề ORBIT STUDIO. Render preview, kiểm tra bố cục rồi xuất MP4 và gửi đường dẫn file.

Với nội dung riêng:

1. Chép ảnh, mô hình `.glb`, nhạc/giọng đọc có sẵn và font vào `assets/`.
2. Gửi prompt, nội dung chữ, tên file và yêu cầu về thời lượng, tỉ lệ khung hình cho Codex.
3. Codex gọi `blender_info`, `list_assets`, lập cảnh và gọi `create_video`.
4. Codex kiểm tra preview, xuất video và theo dõi `video_job_status` đến khi hoàn tất.

Ví dụ:

> Dùng blender tạo clip dọc 8 giây, 720×1280 cho sản phẩm trong assets/product.glb, tiêu đề “Sản phẩm mới”, dùng nhạc assets/music.mp3. Trong JSON, asset ghi là product.glb và audio ghi là music.mp3. Dùng font vietnamese.ttf cho chữ tiếng Việt. Camera tiến gần sản phẩm, sản phẩm xoay nhẹ. Xuất MP4.

Đường dẫn trong JSON tính từ thư mục `assets/`, không có tiền tố `assets/`. Đặt font `.ttf`/`.otf` có đủ ký tự tiếng Việt và khai báo trường `font` để hiển thị dấu đúng.

## Những gì bản này dựng được

- Cube, sphere, cylinder, cone, torus, plane; chữ nổi 3D; ảnh đặt trên mặt phẳng; mô hình GLB.
- Màu sắc, chất liệu kim loại, độ nhám, ánh sáng studio và camera di chuyển.
- Keyframe vị trí, góc xoay và tỉ lệ theo giây; một timeline cho mỗi video.
- Rig xương Blender cho nhân vật hình khối: armature, vertex weights cứng và pose keyframes; camera perspective hoặc orthographic.
- Tự chọn font trên máy có đủ dấu tiếng Việt; nhạc theo từng đoạn và hiệu ứng chim hót, ruồi vo ve, nước nhỏ giọt được tổng hợp theo phong cách hoạt hình.
- Prompt yêu cầu lưu asset sẽ xuất các yếu tố geometry thành GLB trong `assets/generated/video-<job_id>/`, giữ skeleton và thêm vào thư viện. Các pose animation không được xuất; skeleton có thể chỉnh tiếp trong Blender.
- Nhạc hoặc giọng đọc có sẵn; MP4 H.264/AAC, PNG preview và file `.blend` chỉnh sửa tiếp.
- Job nền có trạng thái, tiến độ số frame, log lỗi; khởi động lại MCP không làm mất job đang chạy.

Studio biên soạn prompt thành nhiều shot có geometry, rig và keyframes riêng; renderer thực thi JSON đã được kiểm tra. Chưa sinh footage chân thực, tự gắn xương và skin mềm cho mesh bất kỳ, hoặc điều khiển cửa sổ Blender đang mở. Studio tạo voice riêng; Blender renderer nhận file âm thanh. Render dùng máy cục bộ, thời gian phụ thuộc độ phức tạp và độ phân giải. Mỗi lần sửa/render tạo job mới để giữ lại kết quả trước.

Renderer hiện dùng Cycles trên CPU, 16 samples với denoising để chạy được cả khi máy không có ngữ cảnh đồ họa. Có thể mở `.blend` để chỉnh chất lượng hoặc dùng GPU trong Blender.

## Chạy trực tiếp để kiểm tra

```powershell
.\.venv\Scripts\python.exe -m codex_blender.cli render examples/product.json --mode preview
.\.venv\Scripts\python.exe -m codex_blender.cli render examples/product.json --mode video
.\.venv\Scripts\python.exe -m codex_blender.cli status JOB_ID
```

Kết quả ở `outputs/<job_id>/`: `scene.json`, `scene.blend`, `preview.png`, `frames/`, `video.mp4` (video mode), `render.log`, `status.json`. CLI trả về job ID ngay; chỉ trạng thái `completed` mới xác nhận xong. Frame PNG được giữ lại nên video dài có thể tốn nhiều dung lượng.

Các tool MCP: `blender_info`, `list_assets`, `scene_schema`, `create_video`, `video_job_status`, `video_preview`, `video_job_log`.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/smoke_render.py
```

Smoke test dựng video thật 1 giây, 320×180 và dùng FFmpeg giải mã để kiểm tra MP4. Không cần tài khoản hoặc gọi mô hình khi chạy các kiểm thử này.

Đã kiểm thử trong workspace này với Python 3.13.7, `bpy==5.3.0`, `mcp==1.30.0`: 5 kiểm thử qua và video smoke được render/giải mã thành công. Smoke test dùng primitives/chữ/camera; khả năng nhập GLB, ảnh, font và âm thanh cần kiểm tra thêm với tài nguyên thực tế của bạn.

## Phạm vi truy cập

Renderer nhận mô tả JSON có kiểm tra kiểu dữ liệu, không chạy đoạn Python từ prompt. Assets phải nằm trong thư mục `assets/`; output được lưu trong `outputs/`. Chỉ dùng GLB tự chứa cho mô hình. File `.blend` đầu ra có thể mở bằng Blender; không nhận `.blend` đầu vào có script. MCP dùng stdio, không mở cổng mạng.

Tài liệu giao thức/cách kết nối: [OpenAI MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli). Render nền: [Blender command line](https://docs.blender.org/manual/en/latest/advanced/command_line/render.html).
