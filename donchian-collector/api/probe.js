export default async function handler(_request,response){
  try{
    const upstream=await fetch('https://fapi.binance.com/fapi/v1/time',{signal:AbortSignal.timeout(10000)});
    response.status(upstream.ok?200:502).json({ok:upstream.ok,upstream_status:upstream.status,region:process.env.VERCEL_REGION||null});
  }catch(error){
    response.status(502).json({ok:false,error:error instanceof Error?error.message:'fetch failed',region:process.env.VERCEL_REGION||null});
  }
}
