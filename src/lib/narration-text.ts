const TERMINAL = /[.!?:;,…]["'”’)\]]*$/;

function plainInline(line: string): string {
  return line
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/\[([^\]]+)\]\((?:[^)\s]+)(?:\s+"[^"]*")?\)/g, "$1")
    .replace(/`{1,3}([^`]+)`{1,3}/g, "$1")
    .replace(/(\*\*|__)(?=\S)([\s\S]*?\S)\1/g, "$2")
    .replace(/(^|[^\w*])\*(?=\S)([^*\n]*?\S)\*(?![\w*])/g, "$1$2")
    .replace(/(^|[^\w_])_(?=\S)([^_\n]*?\S)_(?![\w_])/g, "$1$2")
    .replace(/~~(?=\S)([\s\S]*?\S)~~/g, "$1")
    .replace(/\*{2,}|_{2,}/g, "")
    .replace(/(^|\s)\*(?=\S)|(?<=\S)\*(?=\s|$|[.,!?;:])/g, "$1")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

function sentence(text: string): string {
  return text && !TERMINAL.test(text) ? `${text}.` : text;
}

export function normalizeNarration(raw: string, options: { keepHeadings?: boolean } = {}): string {
  const out: string[] = [];
  for (const source of raw.replace(/\r\n?/g, "\n").split("\n")) {
    let line = source.replace(/\u00a0/g, " ");
    if (/^\s*(```|~~~)/.test(line) || /^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) continue;
    const heading = /^\s*(#{1,6})\s+(.*?)\s*#*\s*$/.exec(line);
    if (heading) {
      const text = plainInline(heading[2]);
      if (text) out.push(options.keepHeadings ? `${heading[1]} ${text}` : sentence(text));
      continue;
    }
    line = line.replace(/^\s*(>\s*)+/, "");
    const item = /^\s*(?:[-*+•▪●]|\d{1,3}[.)])\s+(.*)$/.exec(line);
    out.push(item ? sentence(plainInline(item[1])) : plainInline(line));
  }
  return out.join("\n").replace(/\n{3,}/g, "\n\n").trim();
}
