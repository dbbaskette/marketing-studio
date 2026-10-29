/* Raw provider-shaped replies through the real phone UI, compositor and renderer. */
const {execFileSync} = require('node:child_process');
const path = require('node:path');
for(const scenario of ['paraphrase','process','numeric_strings','zeros','calculation','recovery']){
  console.log('Workflow contract: '+scenario);
  execFileSync(process.execPath,[path.join(__dirname,'journey.cjs')],{
    stdio:'inherit',timeout:180000,
    env:{...process.env,INFOGRAPHIC_STUDIO_TEST_SCENARIO:scenario,
      INFOGRAPHIC_STUDIO_TEST_VISUAL:'',INFOGRAPHIC_STUDIO_TEST_SLIDES:'',
      INFOGRAPHIC_STUDIO_TEST_REMOTE:['paraphrase','calculation'].includes(scenario)?'1':'',
      INFOGRAPHIC_UI_RESULTS:process.env.INFOGRAPHIC_UI_RESULTS?path.join(process.env.INFOGRAPHIC_UI_RESULTS,scenario):''},
  });
}
