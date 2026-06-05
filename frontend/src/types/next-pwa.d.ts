declare module 'next-pwa' {
  const withPWAInit: (config: any) => (nextConfig: any) => any;
  export default withPWAInit;
}
