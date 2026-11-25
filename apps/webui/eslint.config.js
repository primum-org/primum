import vue from "eslint-plugin-vue";
import ts from "typescript-eslint";

export default ts.config(
  { ignores: ["src/generated/", "node_modules/", "dist/"] },
  ...ts.configs.strict,
  ...vue.configs["flat/recommended"],
  {
    files: ["**/*.vue"],
    languageOptions: { parserOptions: { parser: ts.parser } },
  },
  {
    rules: {
      // Formatting is not this linter's: these only argue about line breaks.
      "vue/max-attributes-per-line": "off",
      "vue/singleline-html-element-content-newline": "off",
      "vue/html-self-closing": "off",
    },
  },
);
