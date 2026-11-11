import { chromium } from 'playwright-core';

const launch = chromium.launch.bind(chromium);
chromium.launch = async (...options) => {
    const browser = await launch(...options);
    const newContext = browser.newContext.bind(browser);
    const externalOrigins = [];
    browser.newContext = async (...contextOptions) => {
        const context = await newContext(...contextOptions);
        context.on('request', request => {
            const url = new URL(request.url());
            if (['http:', 'https:'].includes(url.protocol) && url.hostname !== '127.0.0.1') {
                externalOrigins.push(url.origin);
            }
        });
        return context;
    };
    browser.on('disconnected', () => {
        console.log('External gateway browser request attempts:', externalOrigins.length, JSON.stringify(externalOrigins));
    });
    return browser;
};
