import { useEffect, useState } from "react";

export function useTradingClock() {
  const [istTime, setIstTime] = useState<string>("");
  const [elapsed, setElapsed] = useState<string>("--:--:--");
  const [remaining, setRemaining] = useState<string>("--:--:--");

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      // IST is UTC+5:30
      const utc = now.getTime() + now.getTimezoneOffset() * 60000;
      const istDate = new Date(utc + 3600000 * 5.5);

      const h = String(istDate.getHours()).padStart(2, "0");
      const m = String(istDate.getMinutes()).padStart(2, "0");
      const s = String(istDate.getSeconds()).padStart(2, "0");
      setIstTime(`${h}:${m}:${s} IST`);

      // 09:27:00 in seconds: 9 * 3600 + 27 * 60 = 34020
      const nowSec = istDate.getHours() * 3600 + istDate.getMinutes() * 60 + istDate.getSeconds();
      const startSec = 9 * 3600 + 27 * 60;
      // 15:13:00 in seconds: 15 * 3600 + 13 * 60 = 54780
      const exitSec = 15 * 3600 + 13 * 60;

      if (nowSec >= startSec && nowSec <= exitSec) {
        const el = nowSec - startSec;
        const eh = Math.floor(el / 3600);
        const em = Math.floor((el % 3600) / 60);
        const es = el % 60;
        setElapsed(`${String(eh).padStart(2, "0")}:${String(em).padStart(2, "0")}:${String(es).padStart(2, "0")}`);

        const rem = exitSec - nowSec;
        const rh = Math.floor(rem / 3600);
        const rm = Math.floor((rem % 3600) / 60);
        const rs = rem % 60;
        setRemaining(`${String(rh).padStart(2, "0")}:${String(rm).padStart(2, "0")}:${String(rs).padStart(2, "0")}`);
      } else if (nowSec < startSec) {
        setElapsed("00:00:00");
        setRemaining("Session Pending");
      } else {
        setElapsed("05:46:00");
        setRemaining("Session Ended");
      }
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return { istTime, elapsed, remaining };
}
