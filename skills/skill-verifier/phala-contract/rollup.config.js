import typescript from '@rollup/plugin-typescript';

export default {
  input: 'src/index.ts',
  output: {
    file: 'dist/index.js',
    format: 'cjs',
    exports: 'auto'
  },
  plugins: [
    typescript()
  ],
  external: ['@phala/pink-env']
};
