const fs = require('fs');
const file = 'd:/에이전트그룹/쇼핑몰/frontend/src/components/ProductStudio.tsx';

let data = fs.readFileSync(file, 'utf8');
data = data.replace(/\{saving \? \<Loader2 size=\{16\} className="animate-spin" \/\> : [^\}]+\}/, '{saving ? <Loader2 size={16} className="animate-spin" /> : "저장하기"}');

fs.writeFileSync(file, data);
console.log('Fixed syntax error in ProductStudio.tsx');
