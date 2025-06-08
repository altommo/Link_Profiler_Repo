import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import typescriptEslint from '@typescript-eslint/eslint-plugin'
import typescriptParser from '@typescript-eslint/parser'

export default [
  { ignores: ['dist'] },
  {
    files: ['**/*.{js,jsx,ts,tsx}'], // Include TypeScript files
    languageOptions: {
      ecmaVersion: 2020,
      sourceType: 'module',
      globals: globals.browser,
      parser: typescriptParser, // Use TypeScript parser
      parserOptions: {
        ecmaFeatures: { jsx: true },
        project: './tsconfig.json', // Specify tsconfig for type-aware linting
        tsconfigRootDir: import.meta.dirname, // Set root directory for tsconfig
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      '@typescript-eslint': typescriptEslint, // Add TypeScript plugin
    },
    rules: {
      ...js.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      ...typescriptEslint.configs.recommended.rules, // Add recommended TypeScript rules
      'no-unused-vars': 'off', // Turn off base rule, use TS version
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^[A-Z_]' }], // TS specific unused vars
      'react-refresh/only-export-components': [
        'warn',
        { allowConstantExport: true },
      ],
      // Add any other specific rules or overrides here
    },
  },
]
