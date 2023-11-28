var root = document.getElementById("root");
var video = document.createElement("video");
let intervalId;
video.autoplay = true;
video.width = 640;
video.height = 480;

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

// video.addEventListener("play", (e) => {
//   const canvas = document.createElement("canvas");
//   canvas.width = e.target.width;
//   canvas.height = e.target.height;
//   const context = canvas.getContext("2d");

//   intervalId = setInterval(() => {
//     context.drawImage(e.target, 0, 0);
//     canvas.toBlob((blob) => {
//       //캔버스의 이미지를 파일 객체로 만드는 과정
//       let file = new File([blob], `${self.crypto.randomUUID()}.jpg`, {
//         type: "image/jpeg",
//       });
//       const formData = new FormData();
//       formData.append("file", file);
//       fetch("/image", {
//         method: "post",
//         body: formData,
//       })
//         .then((res) => res.json())
//         .then((data) => {
//           if (data.statusCode !== 200) {
//             return;
//           }

//           clearInterval(intervalId)

//           Swal.fire({
//             text: "인증 성공",
//             icon: "success",
//           }).then(() => {
//             location.replace(data.url);
//           });
//         })
//         .catch((err) => {
//           console.log(err);
//         });
//     }, "image/jpeg");
//   }, 100);
// });
// var button = document.createElement("button");
// button.textContent = "사진 찍기";
// button.addEventListener("click", () => {
//   const canvas = document.createElement("canvas");
//   canvas.width = video.width;
//   canvas.height = video.height;

//   const context = canvas.getContext("2d");
//   context.drawImage(video, 0, 0);

//   const req = canvas.toBlob((blob) => {
//     //캔버스의 이미지를 파일 객체로 만드는 과정
//     let file = new File([blob], `${self.crypto.randomUUID()}.jpg`, {
//       type: "image/jpeg",
//     });

//     const formData = new FormData();
//     formData.append("file", file);

//     fetch("/image", {
//       method: "post",
//       body: formData,
//     })
//       .then((res) => res.json())
//       .then((data) => {
//         if (data.statusCode !== 200) {

//           return;
//         }

//         Swal.fire({
//           text: "인증 성공",
//           icon: "success",
//         }).then(() => {
//           location.replace(data.url);
//         });
//       })
//       .catch((err) => {
//         console.log(err);
//       });
//   }, "image/jpeg");
// });

const socket = new WebSocket("ws://localhost:8000/ws"); // 서버 주소에 실제 서버 주소를 입력해야 합니다.

video.addEventListener("play", (e) => {
  const canvas = document.createElement("canvas");
  canvas.width = e.target.width;
  canvas.height = e.target.height;
  const context = canvas.getContext("2d");
  const frameRate = 30; // 프레임 레이트 설정

  intervalId = setInterval(() => {
    context.drawImage(e.target, 0, 0, e.target.width, e.target.height);
    canvas.toBlob((blob) => {
      let file = new File([blob], `${self.crypto.randomUUID()}.jpg`, {
        type: "image/jpeg",
      });
      socket.send(file);
    }, "image/jpeg");
  }, 500);
});

// 웹소켓 이벤트 핸들러
socket.onopen = () => {
  console.log("WebSocket 연결됨");
};

socket.onclose = () => {
  console.log("WebSocket 연결 종료");
};

socket.onerror = (error) => {
  console.error("WebSocket 오류 발생:", error);
};

socket.onmessage = (event) => {
  result = JSON.parse(event.data);
  clearInterval(intervalId);
  Swal.fire({
    text: "인증 성공",
    icon: "success",
  }).then(() => {
    socket.close()
    location.replace(result.url);
  });
};

root.appendChild(video);
// root.appendChild(button);
