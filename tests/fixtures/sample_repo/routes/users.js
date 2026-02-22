const express = require("express");
const router = express.Router();

router.get("/users", (_req, res) => {
  res.json([{ id: 1, name: "Ada" }]);
});

module.exports = router;
