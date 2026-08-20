import puppeteer from 'puppeteer-core';

const executablePath = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const outPath = '/Users/gani/Desktop/Intent-drive/living-systems-auditor/artifacts/demos/lsa-demo-walkthrough.webm';

const browser = await puppeteer.launch({
  executablePath,
  headless: true,
  defaultViewport: { width: 1440, height: 900, deviceScaleFactor: 1 },
  args: ['--no-sandbox', '--disable-gpu'],
});

const page = await browser.newPage();
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function smoothScroll(total = 900, step = 90, delay = 120) {
  for (let y = 0; y <= total; y += step) {
    await page.evaluate((scrollTop) => {
      window.scrollTo({ top: scrollTop, behavior: 'instant' });
    }, y);
    await sleep(delay);
  }
}

async function clickButtonByText(label) {
  const clicked = await page.evaluate((text) => {
    const button = [...document.querySelectorAll('button')].find((node) =>
      node.textContent?.trim().includes(text),
    );
    if (!button) {
      return false;
    }
    button.click();
    return true;
  }, label);
  return clicked;
}

await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle2' });
const recorder = await page.screencast({ path: outPath });

await sleep(1200);
await smoothScroll(1200, 120, 140);
await sleep(800);

await page.goto('http://127.0.0.1:5173/onboarding', { waitUntil: 'networkidle2' });
await sleep(1400);
await smoothScroll(900, 100, 120);
await sleep(700);

await page.goto('http://127.0.0.1:5173/command', { waitUntil: 'networkidle2' });
await sleep(1800);
await smoothScroll(1000, 110, 130);
await sleep(900);

await page.goto('http://127.0.0.1:5173/targets', { waitUntil: 'networkidle2' });
await sleep(1500);
await page.evaluate(() => {
  const row = [...document.querySelectorAll('button, a, tr, div')].find((node) =>
    node.textContent?.includes('public-echo-pair'),
  );
  row?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
});
await sleep(1200);

if (await clickButtonByText('Validate')) {
  await sleep(5000);
}

if (await clickButtonByText('Canary verify')) {
  await sleep(5000);
}

await smoothScroll(1100, 100, 120);
await sleep(1200);

await recorder.stop();
await browser.close();

console.log(outPath);
