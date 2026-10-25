// Uses the portfolio's existing Playwright test environment, never a personal profile.
const {chromium}=require('playwright');
const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
const output=path.resolve(__dirname,'../tmp/browser-qa');
const results=[];
async function check(name,run){try{await run();results.push({name,status:'pass'});}catch(error){results.push({name,status:'fail',evidence:error.message});}console.log(results.at(-1).status,name);}
const fits=page=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1);
(async()=>{
  fs.mkdirSync(output,{recursive:true});
  const browser=await chromium.launch({headless:true,executablePath:process.env.BROWSER_PATH});
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  page.setDefaultTimeout(10000); const errors=[]; page.on('pageerror',error=>errors.push(error.message));
  try{
    await page.goto('http://127.0.0.1:4188'); await page.locator('#adopt:not(:disabled)').waitFor();
    await check('representative-computed-text-contrast',async()=>{
      const pairs=await page.evaluate(()=>{
        const rgb=color=>color.match(/[\d.]+/g).map(Number);
        const lum=color=>color.slice(0,3).map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4;}).reduce((sum,n,i)=>sum+n*[.2126,.7152,.0722][i],0);
        return ['.brand strong','.brand div>span','.version','.boundary','h1','.help','.session-meta','.evidence-card strong','.gaps li','.primary','.draft-status'].map(selector=>{
          const el=document.querySelector(selector),chain=[];for(let item=el;item;item=item.parentElement)chain.unshift(item);
          let bg=[255,255,255];chain.forEach(item=>{const c=rgb(getComputedStyle(item).backgroundColor),a=c[3]??1;bg=bg.map((n,i)=>c[i]*a+n*(1-a));});
          const style=getComputedStyle(el),fg=rgb(style.color),a=fg[3]??1,x=lum(bg.map((n,i)=>fg[i]*a+n*(1-a))),y=lum(bg);
          const large=parseFloat(style.fontSize)>=24||(parseFloat(style.fontSize)>=18.66&&Number(style.fontWeight)>=700);
          return {selector,ratio:(Math.max(x,y)+.05)/(Math.min(x,y)+.05),minimum:large?3:4.5};
        });
      });fs.writeFileSync(path.join(output,'contrast.json'),JSON.stringify(pairs,null,2));assert.deepEqual(pairs.filter(row=>row.ratio<row.minimum),[]);
    });
    for(const width of [320,375,768,1440])await check(`layout-${width}`,async()=>{
      await page.setViewportSize({width,height:1000});await page.waitForTimeout(100);assert.equal(await fits(page),true);
      await page.screenshot({path:path.join(output,`workbench-${width}.png`),fullPage:true});
      if(width===1440)await page.screenshot({path:path.join(output,'workbench-desktop.png')});
    });
    await check('200-percent-text',async()=>{
      await page.setViewportSize({width:375,height:1000});await page.waitForTimeout(100);
      await page.evaluate(()=>{const sizes=[...document.querySelectorAll('*')].map(el=>[el,parseFloat(getComputedStyle(el).fontSize)]);sizes.forEach(([el,size])=>el.style.setProperty('font-size',`${size*2}px`,'important'));});
      assert.equal(await fits(page),true);await page.screenshot({path:path.join(output,'text200.png'),fullPage:true});
    });
    await page.reload();await page.locator('#adopt:not(:disabled)').waitFor();
    await check('text-spacing',async()=>{
      await page.evaluate(()=>{for(const el of document.querySelectorAll('*')) {el.style.setProperty('line-height','1.5','important');el.style.setProperty('letter-spacing','.12em','important');el.style.setProperty('word-spacing','.16em','important');if(el.tagName==='P')el.style.setProperty('margin-bottom','2em','important');}});
      assert.equal(await fits(page),true);await page.screenshot({path:path.join(output,'spacing.png'),fullPage:true});
    });
    await page.reload();await page.locator('#adopt:not(:disabled)').waitFor();
    await check('keyboard-and-reduced-motion',async()=>{
      await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>document.activeElement.className),'skip');
      await page.keyboard.press('Enter');assert.equal(await page.evaluate(()=>document.activeElement.id),'workspace');
      assert.equal(await page.evaluate(()=>matchMedia('(prefers-reduced-motion:reduce)').matches),true);
      await page.locator('[data-view="trace"]').focus();await page.keyboard.press('Enter');
      assert.equal(await page.locator('#trace-view').isVisible(),true);
    });
    await check('five-services-and-six-cases',async()=>{
      for(let index=1;index<=6;index++){
        await page.locator(`[data-sid="DEMO-00${index}"]`).click();
        await page.waitForFunction(id=>document.querySelector('#json').textContent.includes(`"sid": "${id}"`),`DEMO-00${index}`);
        assert.equal(await page.locator('#evidence .evidence-card').count()>=2,true);
      }
    });
    await check('cutoff-does-not-leak-future-evidence',async()=>{
      await page.locator('#cutoff').selectOption('2');await page.waitForFunction(()=>document.querySelector('#json').textContent.includes('"upto_seq": 2'));
      assert.equal(await page.locator('#evidence').textContent().then(text=>text.includes('E4')),false);
      await page.locator('#cutoff').selectOption('3');await page.waitForFunction(()=>document.querySelector('#json').textContent.includes('"upto_seq": 3'));
      assert.match(await page.locator('#evidence').textContent(),/E4/);
    });
    await check('human-draft-survives-analysis-and-session-switch',async()=>{
      await page.locator('#draft').fill('人工修改的合成回复，请保留。');await page.locator('#analyze').click();await page.locator('#analyze:not(:disabled)').waitFor();
      assert.equal(await page.locator('#draft').inputValue(),'人工修改的合成回复，请保留。');
      await page.locator('[data-sid="DEMO-001"]').click();await page.locator('[data-sid="DEMO-006"]').click();
      assert.equal(await page.locator('#draft').inputValue(),'人工修改的合成回复，请保留。');
    });
    await check('high-risk-checks-and-invalidation',async()=>{
      await page.locator('[data-sid="DEMO-002"]').click();await page.locator('#review-checks').waitFor();
      assert.equal(await page.locator('#adopt').isDisabled(),true);assert.equal(await page.locator('#copy').isDisabled(),true);
      await page.locator('#check-evidence').check();await page.locator('#check-safe').check();assert.equal(await page.locator('#adopt').isEnabled(),true);
      await page.locator('#draft').fill('合成人工终稿');assert.equal(await page.locator('#adopt').isDisabled(),true);
      await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:path.join(output,'review-desktop.png')});
    });
    await check('adoption-and-unsafe-final-text',async()=>{
      await page.locator('[data-sid="DEMO-001"]').click();await page.locator('#replace').click();await page.locator('#adopt').click();
      await page.getByText('原样采纳已保存在本地；未发送，源工单状态未改变。',{exact:true}).waitFor();
      await page.locator('#draft').fill('保证退款，立即到账');await page.locator('#adopt').click();await page.getByText(/UNSAFE_DRAFT/).waitFor();
      assert.equal(await page.locator('#draft').inputValue(),'保证退款，立即到账');
      await page.locator('#draft').fill('人工核对后的合成回复。');await page.locator('#adopt').click();
      await page.getByText('改写采纳已保存在本地；未发送，源工单状态未改变。',{exact:true}).waitFor();
      await page.locator('#reject').click();await page.getByText('拒绝建议已保存在本地；未发送，源工单状态未改变。',{exact:true}).waitFor();
    });
    await check('state-does-not-claim-sent-or-closed',async()=>{
      await page.locator('[data-view="state"]').click();assert.match(await page.locator('#states').textContent(),/开放/);assert.match(await page.locator('#states').textContent(),/未发送/);
    });
    await check('network-error-retains-draft',async()=>{
      await page.route('**/api/analyze',route=>route.abort());await page.locator('#analyze').click();await page.locator('#error').getByText(/草稿仍保留/).waitFor();
      assert.equal(await page.locator('#draft').inputValue(),'人工核对后的合成回复。');await page.unroute('**/api/analyze');
      assert.equal(await page.locator('#adopt').isDisabled(),true);await page.locator('#retry').click();await page.locator('#adopt:not(:disabled)').waitFor();
    });
    await check('json-narrow-screen',async()=>{
      await page.setViewportSize({width:320,height:1000});await page.locator('.json > summary').click();await page.waitForTimeout(100);assert.equal(await fits(page),true);
    });
    await check('no-script-errors',async()=>assert.deepEqual(errors,[]));
  }finally{await browser.close();}
  fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));
  if(results.some(row=>row.status==='fail'))process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
