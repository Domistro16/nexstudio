const model = process.env.NEXMIND_CREATIVE_MODEL;
const base = process.env.NEXMIND_CREATIVE_BASE_URL.replace(/\/$/, "");

fetch(base + "/chat/completions", {
  method: "POST",
  headers: {
    "Authorization": "Bearer " + process.env.NEXMIND_API_KEY,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    model: model,
    messages: [{
      role: "user",
      content: [
        {
          type: "text",
          text: "Describe this image in one sentence."
        },
        {
          type: "image_url",
          image_url: {
            url: "https://www.gstatic.com/webp/gallery/1.jpg"
          }
        }
      ]
    }]
  })
})
.then(async r => {
  console.log("HTTP", r.status);
  console.log(await r.text());
})
.catch(err => {
  console.error(err);
  process.exit(1);
});