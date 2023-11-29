let intervalId;
let socket;

const video = document.querySelector("#videoElement");
video.autoplay = true

if (navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices
        .getUserMedia({ video: true })
        .then(function (stream) {
            video.srcObject = stream;

        })
        .catch(function (error) {
            console.log("Something went wrong!", error);
        });
}

video.addEventListener("play", (e) => {
    socket = new WebSocket("ws://localhost:8000/ws");  // 서버 주소에 실제 서버 주소를 입력해야 합니다.
    const canvas = document.createElement("canvas");
    canvas.width = video.clientWidth;
    canvas.height = video.clientHeight;
    const context = canvas.getContext("2d");
    const FRAME_RATE = 30; // 프레임 레이트 설정
    const PER_SECOND = 1000

    // 웹소켓 이벤트 핸들러
    socket.onopen = () => {
        console.log("WebSocket 연결됨");
        intervalId = setInterval(() => {
            context.drawImage(e.target, 0, 0);
            canvas.toBlob((blob) => {
                let file = new File([blob], `${self.crypto.randomUUID()}.jpg`, {
                    type: "image/jpeg",
                });

                socket.send(file);
            }, "image/jpeg");
        }, PER_SECOND);
    };

    socket.onclose = () => {
        console.log("WebSocket 연결 종료");
    };

    socket.onerror = (error) => {
        console.error("WebSocket 오류 발생:", error);

        Swal.fire({
            text: '웹소켓 연결 오류가 발생했습니다.',
            icon: 'error',
        });
    };

    socket.onmessage = (event) => {
        result = JSON.parse(event.data);
        socket.close()

        clearInterval(intervalId);

        Swal.fire({
            text: result.data,
            icon: "success",
        }).then(() => {
            video.pause()
            
            location.replace(result.url);
        });
    };
});
