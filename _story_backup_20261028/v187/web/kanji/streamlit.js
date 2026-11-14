/* Streamlit とのやりとり（カスタムコンポーネントの約束ごと）。 */
const Streamlit = (() => {
  const send = (type, data) => window.parent.postMessage({ isStreamlitMessage: true, type, ...data }, "*");
  let onRender = null;
  let lastHeight = -1;

  window.addEventListener("message", (e) => {
    if (e.data && e.data.type === "streamlit:render" && onRender) onRender(e.data.args || {});
  });

  function setHeight() {
    const h = Math.ceil(document.body.getBoundingClientRect().height) + 4;
    if (h !== lastHeight) {
      lastHeight = h;
      send("streamlit:setFrameHeight", { height: h });
    }
  }

  return {
    ready(cb) {
      onRender = cb;
      send("streamlit:componentReady", { apiVersion: 1 });
      new ResizeObserver(setHeight).observe(document.body);
      setHeight();
    },
    setValue(value) {
      send("streamlit:setComponentValue", { value, dataType: "json" });
    },
    setHeight,
  };
})();
