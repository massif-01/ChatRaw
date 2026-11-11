// Launch the loopback-only fixture and wait for its printed ephemeral port.
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';

export async function startFixture(script, { cwd, env = {} } = {}) {
    const child = spawn(process.env.PYTHON || 'python3', ['-B', script], {
        cwd, env: { ...process.env, ...env }, stdio: ['ignore', 'pipe', 'inherit']
    });
    const stop = async () => {
        if (child.exitCode !== null || child.signalCode !== null || !child.pid) return;
        const exited = new Promise(resolve => child.once('exit', resolve));
        child.kill();
        await exited;
    };
    try {
        const port = await new Promise((resolve, reject) => {
            let output = '';
            const timer = setTimeout(() => reject(new Error('Fixture did not announce a port')), 12000);
            const finish = (callback, value) => {
                clearTimeout(timer);
                child.stdout.off('data', read);
                callback(value);
            };
            const read = chunk => {
                output += chunk;
                const match = output.match(/^PORT (\d+)$/m);
                if (match) finish(resolve, match[1]);
            };
            child.stdout.on('data', read);
            child.once('error', error => finish(reject, error));
            child.once('exit', code => finish(reject, new Error('Fixture exited with status ' + code)));
        });
        const origin = 'http://127.0.0.1:' + port;
        for (let attempt = 0; attempt < 60; attempt++) {
            if (await fetch(origin).then(response => response.ok).catch(() => false)) return { origin, stop };
            await delay(100);
        }
        throw new Error('Fixture did not serve its browser page');
    } catch (error) {
        await stop();
        throw error;
    }
}
