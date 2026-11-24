export async function api(path, body) {
  const response = await fetch(
    "/api/" + path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const data = await response.json();
  if (!response.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : "Request failed. Check the claim and try again.",
    );
  return data;
}
export function download(report) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = "TruthTrace-" + report.id + ".json";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
