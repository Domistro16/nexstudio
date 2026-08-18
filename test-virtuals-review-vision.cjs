async function test(label, model) {
  const base = "https://compute.virtuals.io/v1";

  const r = await fetch(base + "/chat/completions", {
    method: "POST",
    headers: {
      Authorization: "Bearer " + process.env.NEXMIND_API_KEY,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      model,
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
  });

  console.log("\n" + label, "HTTP", r.status);
  console.log(await r.text());
}

(async () => {
  await test(
    "SOL VISION",
    "openai-gpt-56-sol"
  );

  await test(
    "SOL PRO VISION",
    "openai-gpt-56-sol-pro"
  );
})();