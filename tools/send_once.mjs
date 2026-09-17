import * as Lark from '@larksuiteoapi/node-sdk';
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path';
const cred = JSON.parse(fs.readFileSync(path.join(os.homedir(),'.dsh','credentials','shouheng-lark.json'),'utf8'));
const client = new Lark.Client({ appId: cred.app_id, appSecret: cred.app_secret });
const text = process.argv.slice(2).join(' ');
const r = await client.im.message.create({
  params: { receive_id_type: 'chat_id' },
  data: { receive_id: 'oc_49a7cfb2861cffa4365ca8491f398d32', msg_type: 'text',
          content: JSON.stringify({ text }) },
});
console.log('已发送:', r?.data?.message_id);
